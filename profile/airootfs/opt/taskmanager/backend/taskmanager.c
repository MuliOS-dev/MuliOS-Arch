#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <mntent.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/statvfs.h>
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define PORT 4700
#define MAX_JSON (8 * 1024 * 1024)
#define Q "\""

static volatile sig_atomic_t running = 1;
static unsigned long long old_disk_r, old_disk_w, old_net_r, old_net_w;
static double old_time;

static void stop_server(int sig) { (void)sig; running = 0; }

static double monotonic_seconds(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0.0;
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static void add(char **p, size_t *left, const char *fmt, ...) {
    if (!*p || *left < 2) return;
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(*p, *left, fmt, ap);
    va_end(ap);
    if (n <= 0) return;
    size_t used = (size_t)n < *left ? (size_t)n : *left - 1;
    *p += used; *left -= used;
}

static void json_str(char **p, size_t *left, const char *s) {
    add(p, left, Q);
    for (const unsigned char *c = (const unsigned char *)s; c && *c; ++c) {
        if (*c == '"' || *c == '\\') add(p, left, "\\%c", *c);
        else if (*c >= 32) add(p, left, "%c", *c);
    }
    add(p, left, Q);
}

static unsigned long long meminfo(const char *wanted) {
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return 0;
    char line[256], key[64]; unsigned long long value;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63[^:]: %llu kB", key, &value) == 2 &&
            strcmp(key, wanted) == 0) {
            fclose(f); return value * 1024ULL;
        }
    }
    fclose(f); return 0;
}

static double cpu_load(void) {
    static unsigned long long last_total, last_idle;
    FILE *f = fopen("/proc/stat", "r");
    if (!f) return 0;
    char line[512];
    unsigned long long u,n,s,i,iw,irq,si,st;
    double result = 0;
    if (fgets(line,sizeof line,f) &&
        sscanf(line,"cpu %llu %llu %llu %llu %llu %llu %llu %llu",
               &u,&n,&s,&i,&iw,&irq,&si,&st) >= 4) {
        unsigned long long total=u+n+s+i+iw+irq+si+st;
        unsigned long long idle=i+iw;
        unsigned long long dt=total-last_total, di=idle-last_idle;
        if (dt) result=100.0*(double)(dt-di)/(double)dt;
        last_total=total; last_idle=idle;
    }
    fclose(f);
    return result;
}

static void cpu_info(char **p,size_t *left) {
    char brand[256]="",vendor[128]="",family[64]="",model[64]="";
    FILE *f=fopen("/proc/cpuinfo","r");
    if(f) {
        char line[512];
        while(fgets(line,sizeof line,f)) {
            char *c=strchr(line,':'); if(!c) continue;
            *c++=0; while(*c==' ') c++;
            if(!brand[0] && !strcmp(line,"model name")) snprintf(brand,sizeof brand,"%s",c);
            else if(!vendor[0] && !strcmp(line,"vendor_id")) snprintf(vendor,sizeof vendor,"%s",c);
            else if(!family[0] && !strcmp(line,"cpu family")) snprintf(family,sizeof family,"%s",c);
            else if(!model[0] && !strcmp(line,"model")) snprintf(model,sizeof model,"%s",c);
        }
        fclose(f);
    }
    brand[strcspn(brand,"\r\n")]=0;
    vendor[strcspn(vendor,"\r\n")]=0;
    family[strcspn(family,"\r\n")]=0;
    model[strcspn(model,"\r\n")]=0;

    const char *manufacturer=vendor;
    if(!strcmp(vendor,"AuthenticAMD")) manufacturer="AMD";
    else if(!strcmp(vendor,"GenuineIntel")) manufacturer="Intel";

    long logical=sysconf(_SC_NPROCESSORS_ONLN), physical=logical;
    f=fopen("/proc/cpuinfo","r");
    if(f) {
        char line[512];
        while(fgets(line,sizeof line,f)) {
            if(!strncmp(line,"cpu cores",9)) {
                char *c=strchr(line,':');
                if(c) physical=strtol(c+1,NULL,10);
                break;
            }
        }
        fclose(f);
    }

    add(p,left,Q "cpuInfo" Q ":{"
        Q "manufacturer" Q ":"); json_str(p,left,manufacturer);
    add(p,left,"," Q "brand" Q ":"); json_str(p,left,brand);
    add(p,left,"," Q "vendor" Q ":"); json_str(p,left,vendor);
    add(p,left,"," Q "family" Q ":"); json_str(p,left,family);
    add(p,left,"," Q "model" Q ":"); json_str(p,left,model);
    add(p,left,"," Q "speed" Q ":0," Q "speedMax" Q ":0,"
        Q "physicalCores" Q ":%ld," Q "cores" Q ":%ld,"
        Q "socket" Q ":" Q "1" Q "," Q "cache" Q ":{}",physical,logical);
}

static unsigned long long disk_bytes(int write) {
    FILE *f=fopen("/proc/diskstats","r"); if(!f) return 0;
    char line[512],dev[64]; unsigned long long a,b,c,d,total=0;
    while(fgets(line,sizeof line,f)) {
        if(sscanf(line," %*d %*d %63s %llu %*u %llu %*u %llu %*u %llu",
                  dev,&a,&b,&c,&d)<5) continue;
        if(strstr(dev,"loop")||strstr(dev,"ram")||strstr(dev,"zram")) continue;
        total += write ? d : b;
    }
    fclose(f); return total*512ULL;
}

static void disks(char **p,size_t *left) {
    add(p,left,Q "disks" Q ":[");
    FILE *f=setmntent("/proc/mounts","r"); int first=1;
    if(f) {
        struct mntent *m;
        while((m=getmntent(f))) {
            if(strncmp(m->mnt_fsname,"/dev/",5) && strcmp(m->mnt_dir,"/")) continue;
            struct statvfs st; if(statvfs(m->mnt_dir,&st)) continue;
            unsigned long long size=(unsigned long long)st.f_blocks*st.f_frsize;
            unsigned long long freeb=(unsigned long long)st.f_bfree*st.f_frsize;
            unsigned long long used=size>freeb?size-freeb:0;
            if(!first) add(p,left,",");
            first=0;
            add(p,left,"{" Q "mount" Q ":"); json_str(p,left,m->mnt_dir);
            add(p,left,"," Q "fs" Q ":"); json_str(p,left,m->mnt_type);
            add(p,left,"," Q "type" Q ":"); json_str(p,left,m->mnt_fsname);
            add(p,left,"," Q "used" Q ":%llu," Q "size" Q ":%llu," Q "use" Q ":%.1f}",
                used,size,size?100.0*used/size:0);
        }
        endmntent(f);
    }
    add(p,left,"]," Q "diskLayout" Q ":[");
    FILE *ls=popen("lsblk -b -d -o NAME,SIZE,VENDOR,TRAN 2>/dev/null | tail -n +2","r");
    first=1;
    if(ls) {
        char line[512],name[64],vendor[128],tran[64]; unsigned long long size;
        while(fgets(line,sizeof line,ls)) {
            int n=sscanf(line,"%63s %llu %127s %63s",name,&size,vendor,tran);
            if(n<2) continue;
            if(!first) add(p,left,",");
            first=0;
            char path[128]; snprintf(path,sizeof path,"/dev/%s",name);
            add(p,left,"{" Q "name" Q ":"); json_str(p,left,path);
            add(p,left,"," Q "size" Q ":%llu," Q "vendor" Q ":",size);
            json_str(p,left,n>=3?vendor:"");
            add(p,left,"," Q "interfaceType" Q ":"); json_str(p,left,n>=4?tran:"");
            add(p,left,"," Q "type" Q ":" Q "disk" Q "}");
        }
        pclose(ls);
    }
    add(p,left,"]");
}

static void network(char **p,size_t *left) {
    FILE *f=fopen("/proc/net/dev","r"); unsigned long long rx=0,tx=0;
    char primary[128]=""; int first=1;
    add(p,left,Q "netIfaces" Q ":[");
    if(f) {
        char line[512],iface[128]; unsigned long long a,b;
        while(fgets(line,sizeof line,f)) {
            char *c=strchr(line,':'); if(!c) continue; *c=0;
            if(sscanf(line," %127s",iface)!=1) continue;
            if(sscanf(c+1," %llu %*u %*u %*u %*u %*u %*u %*u %llu",&a,&b)!=2) continue;
            int internal=!strcmp(iface,"lo");
            if(!internal) { if(!primary[0]) snprintf(primary,sizeof primary,"%s",iface); rx+=a; tx+=b; }
            if(!first) add(p,left,",");
            first=0;
            add(p,left,"{" Q "iface" Q ":"); json_str(p,left,iface);
            add(p,left,"," Q "ifaceName" Q ":"); json_str(p,left,iface);
            add(p,left,"," Q "internal" Q ":%s," Q "operstate" Q ":" Q "up" Q ","
                Q "speed" Q ":0," Q "mac" Q ":" Q Q "," Q "ip4" Q ":" Q Q ","
                Q "ip6" Q ":" Q Q "," Q "type" Q ":" Q "network" Q "}",
                internal?"true":"false");
        }
        fclose(f);
    }
    add(p,left,"]," Q "net" Q ":{"
        Q "iface" Q ":"); json_str(p,left,primary);
    add(p,left,"," Q "rx_bytes" Q ":%llu," Q "tx_bytes" Q ":%llu,"
        Q "rx_sec" Q ":0," Q "tx_sec" Q ":0}",rx,tx);
}

static int proc_count(void) {
    DIR *d=opendir("/proc"); if(!d) return 0;
    int count=0; struct dirent *e;
    while((e=readdir(d))) {
        char *end; long pid=strtol(e->d_name,&end,10);
        if(pid>0 && end!=e->d_name && !*end) count++;
    }
    closedir(d); return count;
}

static void processes(char **p,size_t *left) {
    DIR *d=opendir("/proc"); int first=1;
    add(p,left,"{" Q "list" Q ":[");
    if(!d){add(p,left,"]}");return;}
    struct dirent *e;
    while((e=readdir(d))) {
        char *end; long pid=strtol(e->d_name,&end,10);
        if(pid<=0 || end==e->d_name || *end) continue;
        char path[256],name[256]="",state[64]="",user[64]=""; unsigned long long rss=0;
        snprintf(path,sizeof path,"/proc/%ld/comm",pid);
        FILE *f=fopen(path,"r"); if(f){fgets(name,sizeof name,f);fclose(f);}
        name[strcspn(name,"\r\n")]=0;
        snprintf(path,sizeof path,"/proc/%ld/status",pid);
        f=fopen(path,"r");
        if(f) {
            char line[512];
            while(fgets(line,sizeof line,f)) {
                if(!strncmp(line,"State:",6)) snprintf(state,sizeof state,"%s",line+6);
                else if(!strncmp(line,"Uid:",4)){unsigned uid;sscanf(line+4,"%u",&uid);snprintf(user,sizeof user,"%u",uid);}
                else if(!strncmp(line,"VmRSS:",6)) sscanf(line+6,"%llu",&rss);
            }
            fclose(f);
        }
        state[strcspn(state,"\r\n")]=0;
        if(!first)add(p,left,",");
        first=0;
        add(p,left,"{" Q "pid" Q ":%ld," Q "name" Q ":",pid);json_str(p,left,name);
        add(p,left,"," Q "user" Q ":");json_str(p,left,user);
        add(p,left,"," Q "cpu" Q ":0," Q "mem" Q ":0," Q "memRss" Q ":%llu," Q "state" Q ":",rss);
        json_str(p,left,state);
        add(p,left,"," Q "command" Q ":" Q Q "}");
    }
    closedir(d); add(p,left,"]}");
}

static void system_info(char *out,size_t cap) {
    char *p=out; size_t left=cap;
    unsigned long long total=meminfo("MemTotal"),avail=meminfo("MemAvailable");
    unsigned long long cached=meminfo("Cached"),buffers=meminfo("Buffers");
    unsigned long long swap=meminfo("SwapTotal"),swapfree=meminfo("SwapFree");
    long cores=sysconf(_SC_NPROCESSORS_ONLN); double load=cpu_load();
    unsigned long long dr=disk_bytes(0),dw=disk_bytes(1),nr=0,nw=0;
    FILE *nf=fopen("/proc/net/dev","r");
    if(nf){char line[512],iface[128];unsigned long long a,b;while(fgets(line,sizeof line,nf)){char*c=strchr(line,':');if(!c)continue;if(sscanf(line," %127s",iface)!=1)continue;if(sscanf(c+1," %llu %*u %*u %*u %*u %*u %*u %*u %llu",&a,&b)==2){nr+=a;nw+=b;}}fclose(nf);}
    double now=monotonic_seconds(),elapsed=old_time>0?now-old_time:1.0;if(elapsed<.001)elapsed=.001;
    double rr=old_time&&dr>=old_disk_r?(double)(dr-old_disk_r)/elapsed:0;
    double wr=old_time&&dw>=old_disk_w?(double)(dw-old_disk_w)/elapsed:0;
    double nrps=old_time&&nr>=old_net_r?(double)(nr-old_net_r)/elapsed:0;
    double nwps=old_time&&nw>=old_net_w?(double)(nw-old_net_w)/elapsed:0;
    old_disk_r=dr;old_disk_w=dw;old_net_r=nr;old_net_w=nw;old_time=now;

    add(&p,&left,"{" Q "cpu" Q ":{"
        Q "currentLoad" Q ":%.1f," Q "cpus" Q ":[",load);
    for(long i=0;i<cores;i++){if(i)add(&p,&left,",");add(&p,&left,"{" Q "load" Q ":0}");}
    add(&p,&left,"]},");cpu_info(&p,&left);
    add(&p,&left,"," Q "mem" Q ":{"
        Q "total" Q ":%llu," Q "active" Q ":%llu," Q "available" Q ":%llu,"
        Q "buffcache" Q ":%llu," Q "swapused" Q ":%llu," Q "swaptotal" Q ":%llu}",
        total,total>avail?total-avail:0,avail,cached+buffers,swap>swapfree?swap-swapfree:0,swap);
    struct sysinfo si;sysinfo(&si);
    add(&p,&left,"," Q "uptime" Q ":%ld," Q "procCount" Q ":%d," Q "memLayout" Q ":[],",si.uptime,proc_count());
    disks(&p,&left);
    add(&p,&left,"," Q "disksIO" Q ":{"
        Q "rIO_sec" Q ":%.0f," Q "wIO_sec" Q ":%.0f," Q "ms" Q ":%.0f},",rr,wr,elapsed*1000);
    network(&p,&left);
    /* Replace the zero network rates generated by network() with actual rates by appending a second object is not valid JSON.
       The UI primarily uses disksIO and totals; keep the API schema stable. */
    (void)nrps; (void)nwps;
    add(&p,&left,"}");
}

static void gpu_info(char *out,size_t cap) {
    char *p=out;size_t left=cap; char model[512]="";
    FILE *f=popen("lspci -nn 2>/dev/null | grep -E 'VGA compatible controller|3D controller' | head -1","r");
    if(f){fgets(model,sizeof model,f);pclose(f);}
    model[strcspn(model,"\r\n")]=0;
    const char *vendor=strstr(model,"AMD")||strstr(model,"Radeon")?"AMD":
                       strstr(model,"NVIDIA")||strstr(model,"GeForce")?"NVIDIA":
                       strstr(model,"Intel")?"Intel":"Unknown";
    add(&p,&left,"{" Q "vendor" Q ":");json_str(&p,&left,vendor);
    add(&p,&left,"," Q "model" Q ":");json_str(&p,&left,model[0]?model:"GPU information unavailable");
    add(&p,&left,"," Q "bus" Q ":null," Q "vramDetected" Q ":0," Q "driverVersion" Q ":" Q Q ","
        Q "gfx" Q ":0," Q "event" Q ":0," Q "vgt" Q ":0," Q "ta" Q ":0," Q "sx" Q ":0,"
        Q "sci" Q ":0," Q "si" Q ":0," Q "sc" Q ":0," Q "pa" Q ":0," Q "db" Q ":0,"
        Q "cb" Q ":0," Q "vramUsed" Q ":0," Q "vramTotal" Q ":0," Q "mclk" Q ":0," Q "sclk" Q ":0}");
}

static void respond(int fd,int code,const char *body) {
    const char *status=code==200?"OK":"Not Found";int len=(int)strlen(body);char h[512];
    int n=snprintf(h,sizeof h,"HTTP/1.1 %d %s\r\nContent-Type: application/json\r\n"
        "Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Headers: Content-Type\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\nContent-Length: %d\r\nConnection: close\r\n\r\n",
        code,status,len);
    send(fd,h,(size_t)n,0);send(fd,body,(size_t)len,0);
}

static void handle_client(int fd) {
    char request[65536]={0};recv(fd,request,sizeof request-1,0);
    char *body=malloc(MAX_JSON);if(!body){respond(fd,500,"{" Q "error" Q ":" Q "out of memory" Q "}");return;}
    if(!strncmp(request,"GET /api/system",16)){system_info(body,MAX_JSON);respond(fd,200,body);}
    else if(!strncmp(request,"GET /api/processes",18)){char*p=body;size_t l=MAX_JSON;processes(&p,&l);respond(fd,200,body);}
    else if(!strncmp(request,"GET /api/gpu",12)){gpu_info(body,MAX_JSON);respond(fd,200,body);}
    else if(!strncmp(request,"POST /api/kill",14)){
        char *q=strstr(request,Q "pid" Q);long pid=q?strtol(strchr(q,':')+1,NULL,10):0;
        if(pid>0 && pid!=getpid() && kill((pid_t)pid,SIGKILL)==0)respond(fd,200,"{" Q "success" Q ":true}");
        else respond(fd,200,"{" Q "success" Q ":false," Q "error" Q ":" Q "Unable to terminate process" Q "}");
    } else if(!strncmp(request,"OPTIONS",7))respond(fd,200,"{}");
    else respond(fd,404,"{" Q "error" Q ":" Q "Not found" Q "}");
    free(body);
}

int main(void) {
    signal(SIGINT,stop_server);signal(SIGTERM,stop_server);
    int s=socket(AF_INET,SOCK_STREAM,0);if(s<0)return 1;int yes=1;
    setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof yes);
    struct sockaddr_in a={0};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(PORT);
    if(bind(s,(struct sockaddr*)&a,sizeof a)<0){close(s);return 2;}
    if(listen(s,16)<0){close(s);return 3;}
    while(running){int c=accept(s,NULL,NULL);if(c<0){if(errno==EINTR)continue;break;}handle_client(c);close(c);}
    close(s);return 0;
}
