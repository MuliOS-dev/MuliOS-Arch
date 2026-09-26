#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statvfs.h>
#include <sys/socket.h>
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <unistd.h>

#define PORT 4700
#define BUF_SIZE 65536
#define JSON_SIZE 4194304

static volatile sig_atomic_t running = 1;
static unsigned long long prev_disk_r = 0, prev_disk_w = 0, prev_net_r = 0, prev_net_w = 0;
static double prev_time = 0;

static void stop_server(int sig) { (void)sig; running = 0; }
static double now_seconds(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec / 1e9; }
static unsigned long long read_kb(const char *key) {
    FILE *f = fopen("/proc/meminfo", "r"); if (!f) return 0; char line[256]; unsigned long long v=0; char k[64];
    while (fgets(line,sizeof(line),f)) if (sscanf(line,"%63[^:]: %llu kB",k,&v)==2 && strcmp(k,key)==0) { fclose(f); return v*1024ULL; }
    fclose(f); return 0;
}
static double json_num(char *p, double v) { return sprintf(p,"%.3f",v), v; }
static void append(char **p, size_t *left, const char *fmt, ...) {
    if (*left < 2) return; va_list ap; va_start(ap,fmt); int n=vsnprintf(*p,*left,fmt,ap); va_end(ap); if(n>0){size_t x=(size_t)n<*left?(size_t)n:*left-1;*p+=x;*left-=x;}
}
static void json_escape(char **p,size_t *left,const char *s){append(p,left,"\"");for(;s&&*s;s++){char c=*s;if(c=='\"'||c=='\\')append(p,left,"\\%c",c);else if((unsigned char)c>=32)append(p,left,"%c",c);}append(p,left,"\"");}

static void cpu_info(char **p,size_t *left) {
    FILE *f=fopen("/proc/cpuinfo","r"); char brand[256]="",vendor[128]="",family[32]="",model[32]=""; char line[512];
    if(f){while(fgets(line,sizeof(line),f)){char *c=strchr(line,':');if(!c)continue;*c++=0;while(*c==' ')c++; if(!brand[0]&&!strcmp(line,"model name"))snprintf(brand,sizeof brand,"%s",c); else if(!vendor[0]&&!strcmp(line,"vendor_id"))snprintf(vendor,sizeof vendor,"%s",c); else if(!family[0]&&!strcmp(line,"cpu family"))snprintf(family,sizeof family,"%s",c); else if(!model[0]&&!strcmp(line,"model"))snprintf(model,sizeof model,"%s",c); }fclose(f);}
    brand[strcspn(brand,"\r\n")]=0; vendor[strcspn(vendor,"\r\n")]=0; family[strcspn(family,"\r\n")]=0; model[strcspn(model,"\r\n")]=0;
    const char *man=!strncmp(vendor,"AuthenticAMD",12)?"AMD":!strncmp(vendor,"GenuineIntel",12)?"Intel":vendor;
    long logical=sysconf(_SC_NPROCESSORS_ONLN), physical=0; FILE *t=fopen("/proc/cpuinfo","r"); if(t){char l[512];while(fgets(l,sizeof l,t))if(strstr(l,"cpu cores")){physical=strtol(strchr(l,':')+1,NULL,10);break;}fclose(t);} if(!physical)physical=logical;
    append(p,left,"\"cpuInfo\":{\"manufacturer\":");json_escape(p,left,man);append(p,left,",\"brand\":");json_escape(p,left,brand);append(p,left,",\"vendor\":");json_escape(p,left,vendor);append(p,left,",\"family\":");json_escape(p,left,family);append(p,left,",\"model\":");json_escape(p,left,model);append(p,left,",\"speed\":0,\"speedMax\":0,\"physicalCores\":%ld,\"cores\":%ld,\"socket\":\"1\",\"cache\":{}}",physical,logical);
}

static double cpu_load(void){static unsigned long long last_total=0,last_idle=0;FILE*f=fopen("/proc/stat","r");if(!f)return 0;char l[512];unsigned long long u,n,s,id,iw,iq,si,st;double out=0;if(fgets(l,sizeof l,f)&&sscanf(l,"cpu %llu %llu %llu %llu %llu %llu %llu %llu",&u,&n,&s,&id,&iw,&iq,&si,&st)>=4){unsigned long long total=u+n+s+id+iw+iq+si+st;unsigned long long idle=id+iw;unsigned long long dt=total-last_total,di=idle-last_idle;if(dt)out=100.0*(double)(dt-di)/(double)dt;last_total=total;last_idle=idle;}fclose(f);return out;}

static void filesystem_json(char **p,size_t*left){append(p,left,"\"disks\":[");FILE*f=setmntent("/proc/mounts","r");int first=1;if(f){struct mntent*m;while((m=getmntent(f))){if(strncmp(m->mnt_fsname,"/dev/",5)&&strcmp(m->mnt_dir,"/"))continue;struct statvfs v;if(statvfs(m->mnt_dir,&v))continue;unsigned long long size=(unsigned long long)v.f_blocks*v.f_frsize,freeb=(unsigned long long)v.f_bfree*v.f_frsize,used=size-freeb; if(!first)append(p,left,",");first=0;append(p,left,"{\"mount\":");json_escape(p,left,m->mnt_dir);append(p,left,",\"fs\":");json_escape(p,left,m->mnt_type);append(p,left,",\"type\":");json_escape(p,left,m->mnt_fsname);append(p,left,",\"used\":%llu,\"size\":%llu,\"use\":%.1f}",used,size,size?100.0*used/size:0);}endmntent(f);}append(p,left,"],\"diskLayout\":[]");}

static void network_json(char **p,size_t*left){FILE*f=fopen("/proc/net/dev","r");unsigned long long rx=0,tx=0;char primary[128]="";append(p,left,"\"netIfaces\":[");int first=1;if(f){char l[512];while(fgets(l,sizeof l,f)){char iface[128];unsigned long long a,b;char *c=strchr(l,':');if(!c)continue;*c=0;sscanf(l," %127s",iface);if(sscanf(c+1,"%llu %*u %*u %*u %*u %*u %*u %*u %llu",&a,&b)<2)continue;if(strcmp(iface,"lo")){if(!primary[0])snprintf(primary,sizeof primary,"%s",iface);rx+=a;tx+=b;}if(!first)append(p,left,",");first=0;append(p,left,"{\"iface\":");json_escape(p,left,iface);append(p,left,",\"ifaceName\":");json_escape(p,left,iface);append(p,left,",\"internal\":%s,\"operstate\":\"up\",\"speed\":0,\"mac\":\"\",\"ip4\":\"\",\"ip6\":\"\",\"type\":\"network\"}",strcmp(iface,"lo")==0?"true":"false");}fclose(f);}append(p,left,"],\"net\":{\"iface\":");json_escape(p,left,primary);append(p,left,",\"rx_bytes\":%llu,\"tx_bytes\":%llu,\"rx_sec\":0,\"tx_sec\":0}",rx,tx);}

static void process_json(char **p,size_t*left){DIR*d=opendir("/proc");append(p,left,"{\"list\":[");int first=1;if(!d){append(p,left,"]}");return;}struct dirent*e;while((e=readdir(d))){char*end;long pid=strtol(e->d_name,&end,10);if(*e->d_name==0||*end)continue;char path[256],name[256]="",user[64]="";snprintf(path,sizeof path,"/proc/%ld/comm",pid);FILE*f=fopen(path,"r");if(f){fgets(name,sizeof name,f);fclose(f);}name[strcspn(name,"\r\n")]=0;snprintf(path,sizeof path,"/proc/%ld/status",pid);f=fopen(path,"r");if(f){char l[256];while(fgets(l,sizeof l,f))if(!strncmp(l,"Uid:",4)){unsigned uid;sscanf(l+4,"%u",&uid);snprintf(user,sizeof user,"%u",uid);break;}fclose(f);}if(!first)append(p,left,",");first=0;append(p,left,"{\"pid\":%ld,\"name\":",pid);json_escape(p,left,name);append(p,left,",\"user\":");json_escape(p,left,user);append(p,left,",\"cpu\":0,\"mem\":0,\"memRss\":0,\"state\":\"\",\"command\":\"\"}");}closedir(d);append(p,left,"]}");}

static void system_json(char *out,size_t cap){char*p=out;size_t left=cap;unsigned long long total=read_kb("MemTotal"),avail=read_kb("MemAvailable"),buffers=read_kb("Buffers"),cached=read_kb("Cached"),swap=read_kb("SwapTotal"),swapfree=read_kb("SwapFree");long logical=sysconf(_SC_NPROCESSORS_ONLN);double load=cpu_load();append(&p,&left,"{\"cpu\":{\"currentLoad\":%.1f,\"cpus\":[",load);for(long i=0;i<logical;i++){if(i)append(&p,&left,",");append(&p,&left,"{\"load\":0}");}append(&p,&left,"]},");cpu_info(&p,&left);append(&p,&left,",\"mem\":{\"total\":%llu,\"active\":%llu,\"available\":%llu,\"buffcache\":%llu,\"swapused\":%llu,\"swaptotal\":%llu},",total,total-avail,avail,buffers+cached,swap-(swapfree),swap);struct sysinfo si;sysinfo(&si);append(&p,&left,"\"uptime\":%ld,\"procCount\":%d,\"memLayout\":[],",si.uptime,getpid());filesystem_json(&p,&left);append(&p,&left,",");network_json(&p,&left);append(&p,&left,"}");}

static void gpu_json(char*out,size_t cap){char*p=out;size_t left=cap;FILE*f=popen("lspci -nn 2>/dev/null | grep -E 'VGA compatible|3D controller' | head -1","r");char line[512]="";if(f){fgets(line,sizeof line,f);pclose(f);}line[strcspn(line,"\r\n")]=0;append(&p,&left,"{\"vendor\":\"Unknown\",\"model\":");json_escape(&p,&left,line[0]?line:"GPU information unavailable");append(&p,&left,",\"bus\":null,\"vramDetected\":0,\"driverVersion\":\"\",\"gfx\":0,\"event\":0,\"vgt\":0,\"ta\":0,\"sx\":0,\"sci\":0,\"si\":0,\"sc\":0,\"pa\":0,\"db\":0,\"cb\":0,\"vramUsed\":0,\"vramTotal\":0,\"mclk\":0,\"sclk\":0}");}

static void response(int fd,int code,const char*body){char hdr[256];int n=strlen(body);snprintf(hdr,sizeof hdr,"HTTP/1.1 %d OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: %d\r\nConnection: close\r\n\r\n",code,n);send(fd,hdr,strlen(hdr),0);send(fd,body,n,0);}
static void handle(int fd){char req[BUF_SIZE]={0};recv(fd,req,sizeof req-1,0);char body[JSON_SIZE];if(!strncmp(req,"GET /api/system",16)){system_json(body,sizeof body);response(fd,200,body);}else if(!strncmp(req,"GET /api/processes",19)){process_json(&((char*){0}),&(size_t){0});char*p=body;size_t l=sizeof body;process_json(&p,&l);response(fd,200,body);}else if(!strncmp(req,"GET /api/gpu",12)){gpu_json(body,sizeof body);response(fd,200,body);}else if(!strncmp(req,"OPTIONS",7)){response(fd,200,"{}");}else if(!strncmp(req,"POST /api/kill",14)){response(fd,200,"{\"success\":false,\"error\":\"Use process manager permissions\"}");}else response(fd,404,"{\"error\":\"Not found\"}");}

int main(void){signal(SIGINT,stop_server);signal(SIGTERM,stop_server);int s=socket(AF_INET,SOCK_STREAM,0);if(s<0)return 1;int one=1;setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof one);struct sockaddr_in a={0};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(PORT);if(bind(s,(struct sockaddr*)&a,sizeof a)<0||listen(s,16)<0)return 1;while(running){int c=accept(s,NULL,NULL);if(c>=0){handle(c);close(c);}}close(s);return 0;}
