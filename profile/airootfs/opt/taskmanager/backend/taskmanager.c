#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
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
#define REQ_SIZE 65536
#define JSON_SIZE 8 * 1024 * 1024

static volatile sig_atomic_t running = 1;
static unsigned long long last_disk_read, last_disk_write, last_net_rx, last_net_tx;
static double last_sample;

static void stop_server(int sig) {
    (void)sig;
    running = 0;
}

static double monotonic_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static void append(char **dst, size_t *left, const char *fmt, ...) {
    if (!dst || !*dst || !left || *left < 2) return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(*dst, *left, fmt, ap);
    va_end(ap);
    if (n <= 0) return;
    size_t used = (size_t)n < *left ? (size_t)n : *left - 1;
    *dst += used;
    *left -= used;
}

static void json_string(char **dst, size_t *left, const char *value) {
    append(dst, left, """);
    if (value) {
        for (const unsigned char *p = (const unsigned char *)value; *p; ++p) {
            if (*p == '"' || *p == '\') append(dst, left, "\\%c", *p);
            else if (*p >= 32) append(dst, left, "%c", *p);
        }
    }
    append(dst, left, """);
}

static unsigned long long mem_value(const char *key) {
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return 0;
    char line[256], name[64];
    unsigned long long value;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%63[^:]: %llu kB", name, &value) == 2 &&
            strcmp(name, key) == 0) {
            fclose(f);
            return value * 1024ULL;
        }
    }
    fclose(f);
    return 0;
}

static double cpu_total_load(void) {
    static unsigned long long old_total, old_idle;
    FILE *f = fopen("/proc/stat", "r");
    if (!f) return 0.0;

    char line[512];
    unsigned long long user, nice, system, idle, iowait, irq, softirq, steal;
    double load = 0.0;

    if (fgets(line, sizeof(line), f) &&
        sscanf(line, "cpu %llu %llu %llu %llu %llu %llu %llu %llu",
               &user, &nice, &system, &idle, &iowait, &irq, &softirq, &steal) >= 4) {
        unsigned long long total = user + nice + system + idle + iowait + irq + softirq + steal;
        unsigned long long idle_total = idle + iowait;
        unsigned long long dt = total - old_total;
        unsigned long long di = idle_total - old_idle;
        if (dt) load = 100.0 * (double)(dt - di) / (double)dt;
        old_total = total;
        old_idle = idle_total;
    }

    fclose(f);
    return load;
}

static void cpu_info(char **p, size_t *left) {
    char brand[256] = "";
    char vendor[128] = "";
    char family[64] = "";
    char model[64] = "";

    FILE *f = fopen("/proc/cpuinfo", "r");
    if (f) {
        char line[512];
        while (fgets(line, sizeof(line), f)) {
            char *colon = strchr(line, ':');
            if (!colon) continue;
            *colon++ = '\0';
            while (*colon == ' ') colon++;
            if (!brand[0] && strcmp(line, "model name") == 0) snprintf(brand, sizeof(brand), "%s", colon);
            else if (!vendor[0] && strcmp(line, "vendor_id") == 0) snprintf(vendor, sizeof(vendor), "%s", colon);
            else if (!family[0] && strcmp(line, "cpu family") == 0) snprintf(family, sizeof(family), "%s", colon);
            else if (!model[0] && strcmp(line, "model") == 0) snprintf(model, sizeof(model), "%s", colon);
        }
        fclose(f);
    }

    brand[strcspn(brand, "\r\n")] = 0;
    vendor[strcspn(vendor, "\r\n")] = 0;
    family[strcspn(family, "\r\n")] = 0;
    model[strcspn(model, "\r\n")] = 0;

    const char *manufacturer = vendor;
    if (strcmp(vendor, "AuthenticAMD") == 0) manufacturer = "AMD";
    else if (strcmp(vendor, "GenuineIntel") == 0) manufacturer = "Intel";

    long cores = sysconf(_SC_NPROCESSORS_ONLN);
    long physical = cores;

    f = fopen("/proc/cpuinfo", "r");
    if (f) {
        char line[512];
        while (fgets(line, sizeof(line), f)) {
            if (strncmp(line, "cpu cores", 9) == 0) {
                char *colon = strchr(line, ':');
                if (colon) physical = strtol(colon + 1, NULL, 10);
                break;
            }
        }
        fclose(f);
    }

    append(p, left, ""cpuInfo":{"manufacturer":");
    json_string(p, left, manufacturer);
    append(p, left, ","brand":");
    json_string(p, left, brand);
    append(p, left, ","vendor":");
    json_string(p, left, vendor);
    append(p, left, ","family":");
    json_string(p, left, family);
    append(p, left, ","model":");
    json_string(p, left, model);
    append(p, left, ","speed":0,"speedMax":0,"physicalCores":%ld,"cores":%ld,"socket":"1","cache":{}}",
           physical, cores);
}

static unsigned long long disk_io_value(int write) {
    FILE *f = fopen("/proc/diskstats", "r");
    if (!f) return 0;
    char line[512], device[64];
    unsigned long long reads = 0, sectors_read = 0, writes = 0, sectors_write = 0;
    unsigned long long total = 0;

    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, " %*d %*d %63s %llu %*u %llu %*u %llu %*u %llu",
                   device, &reads, &sectors_read, &writes, &sectors_write) < 5)
            continue;
        if (strstr(device, "loop") || strstr(device, "ram") || strstr(device, "zram"))
            continue;
        total += write ? sectors_write : sectors_read;
    }

    fclose(f);
    return total * 512ULL;
}

static void filesystem_info(char **p, size_t *left) {
    append(p, left, ""disks":[");
    FILE *f = setmntent("/proc/mounts", "r");
    int first = 1;

    if (f) {
        struct mntent *entry;
        while ((entry = getmntent(f))) {
            if (strncmp(entry->mnt_fsname, "/dev/", 5) != 0 &&
                strcmp(entry->mnt_dir, "/") != 0)
                continue;

            struct statvfs st;
            if (statvfs(entry->mnt_dir, &st) != 0) continue;

            unsigned long long size = (unsigned long long)st.f_blocks * st.f_frsize;
            unsigned long long free_bytes = (unsigned long long)st.f_bfree * st.f_frsize;
            unsigned long long used = size > free_bytes ? size - free_bytes : 0;

            if (!first) append(p, left, ",");
            first = 0;

            append(p, left, "{"mount":");
            json_string(p, left, entry->mnt_dir);
            append(p, left, ","fs":");
            json_string(p, left, entry->mnt_type);
            append(p, left, ","type":");
            json_string(p, left, entry->mnt_fsname);
            append(p, left, ","used":%llu,"size":%llu,"use":%.1f}",
                   used, size, size ? 100.0 * (double)used / size : 0.0);
        }
        endmntent(f);
    }

    append(p, left, "],"diskLayout":[");
    FILE *ls = popen("lsblk -b -d -o NAME,SIZE,MODEL,VENDOR,TRAN 2>/dev/null | tail -n +2", "r");
    first = 1;
    if (ls) {
        char line[512], name[64], model[128], vendor[128], transport[64];
        unsigned long long size;
        while (fgets(line, sizeof(line), ls)) {
            memset(name, 0, sizeof(name)); memset(model, 0, sizeof(model));
            memset(vendor, 0, sizeof(vendor)); memset(transport, 0, sizeof(transport));
            int n = sscanf(line, "%63s %llu %127s %127s %63s",
                           name, &size, model, vendor, transport);
            if (n < 2) continue;
            if (!first) append(p, left, ",");
            first = 0;
            append(p, left, "{"name":");
            char dev[160];
            snprintf(dev, sizeof(dev), "/dev/%s", name);
            json_string(p, left, dev);
            append(p, left, ","size":%llu,"vendor":", size);
            json_string(p, left, n >= 4 ? vendor : "");
            append(p, left, ","interfaceType":");
            json_string(p, left, n >= 5 ? transport : "");
            append(p, left, ","type":"disk"}");
        }
        pclose(ls);
    }
    append(p, left, "]");
}

static void network_info(char **p, size_t *left) {
    FILE *f = fopen("/proc/net/dev", "r");
    unsigned long long rx = 0, tx = 0;
    char primary[128] = "";
    int first = 1;

    append(p, left, ""netIfaces":[");
    if (f) {
        char line[512], iface[128];
        unsigned long long irx, itx;

        while (fgets(line, sizeof(line), f)) {
            char *colon = strchr(line, ':');
            if (!colon) continue;
            *colon = '\0';
            if (sscanf(line, " %127s", iface) != 1) continue;
            if (sscanf(colon + 1,
                       " %llu %*u %*u %*u %*u %*u %*u %*u %llu",
                       &irx, &itx) != 2)
                continue;

            int internal = strcmp(iface, "lo") == 0;
            if (!internal && !primary[0]) snprintf(primary, sizeof(primary), "%s", iface);
            if (!internal) { rx += irx; tx += itx; }

            if (!first) append(p, left, ",");
            first = 0;

            append(p, left, "{"iface":");
            json_string(p, left, iface);
            append(p, left, ","ifaceName":");
            json_string(p, left, iface);
            append(p, left, ","internal":%s,"operstate":"up","speed":0,"mac":"","ip4":"","ip6":"","type":"network"}",
                   internal ? "true" : "false");
        }
        fclose(f);
    }

    append(p, left, "],"net":{"iface":");
    json_string(p, left, primary);
    append(p, left, ","rx_bytes":%llu,"tx_bytes":%llu,"rx_sec":0,"tx_sec":0}", rx, tx);
}

static int process_count(void) {
    DIR *dir = opendir("/proc");
    if (!dir) return 0;
    int count = 0;
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        char *end;
        long pid = strtol(entry->d_name, &end, 10);
        if (pid > 0 && end != entry->d_name && *end == '\0') count++;
    }
    closedir(dir);
    return count;
}

static void process_info(char **p, size_t *left) {
    DIR *dir = opendir("/proc");
    append(p, left, "{"list":[");
    int first = 1;

    if (!dir) {
        append(p, left, "]}");
        return;
    }

    struct dirent *entry;
    while ((entry = readdir(dir))) {
        char *end;
        long pid = strtol(entry->d_name, &end, 10);
        if (pid <= 0 || end == entry->d_name || *end != '\0') continue;

        char path[256], name[256] = "", state[32] = "", user[64] = "";
        unsigned long long rss_kb = 0;

        snprintf(path, sizeof(path), "/proc/%ld/comm", pid);
        FILE *f = fopen(path, "r");
        if (f) { fgets(name, sizeof(name), f); fclose(f); }
        name[strcspn(name, "\r\n")] = 0;

        snprintf(path, sizeof(path), "/proc/%ld/status", pid);
        f = fopen(path, "r");
        if (f) {
            char line[512];
            while (fgets(line, sizeof(line), f)) {
                if (strncmp(line, "State:", 6) == 0) snprintf(state, sizeof(state), "%s", line + 6);
                else if (strncmp(line, "Uid:", 4) == 0) {
                    unsigned uid = 0;
                    sscanf(line + 4, "%u", &uid);
                    snprintf(user, sizeof(user), "%u", uid);
                } else if (strncmp(line, "VmRSS:", 6) == 0) sscanf(line + 6, "%llu", &rss_kb);
            }
            fclose(f);
        }
        state[strcspn(state, "\r\n")] = 0;

        if (!first) append(p, left, ",");
        first = 0;
        append(p, left, "{"pid":%ld,"name":", pid);
        json_string(p, left, name);
        append(p, left, ","user":");
        json_string(p, left, user);
        append(p, left, ","cpu":0,"mem":0,"memRss":%llu,"state":", rss_kb);
        json_string(p, left, state);
        append(p, left, ","command":""}");
    }

    closedir(dir);
    append(p, left, "]}");
}

static void system_info(char *out, size_t capacity) {
    char *p = out;
    size_t left = capacity;

    unsigned long long total = mem_value("MemTotal");
    unsigned long long available = mem_value("MemAvailable");
    unsigned long long cached = mem_value("Cached");
    unsigned long long buffers = mem_value("Buffers");
    unsigned long long swap_total = mem_value("SwapTotal");
    unsigned long long swap_free = mem_value("SwapFree");

    long cores = sysconf(_SC_NPROCESSORS_ONLN);
    double load = cpu_total_load();

    unsigned long long disk_read = disk_io_value(0);
    unsigned long long disk_write = disk_io_value(1);
    double now = monotonic_seconds();
    double elapsed = last_sample > 0 ? now - last_sample : 1.0;
    if (elapsed < 0.001) elapsed = 0.001;

    double read_rate = last_sample > 0 && disk_read >= last_disk_read
        ? (double)(disk_read - last_disk_read) / elapsed : 0.0;
    double write_rate = last_sample > 0 && disk_write >= last_disk_write
        ? (double)(disk_write - last_disk_write) / elapsed : 0.0;

    last_disk_read = disk_read;
    last_disk_write = disk_write;
    last_sample = now;

    append(&p, &left, "{"cpu":{"currentLoad":%.1f,"cpus":[", load);
    for (long i = 0; i < cores; ++i) {
        if (i) append(&p, &left, ",");
        append(&p, &left, "{"load":0}");
    }
    append(&p, &left, "]},");
    cpu_info(&p, &left);

    append(&p, &left, ","mem":{"total":%llu,"active":%llu,"available":%llu,"buffcache":%llu,"swapused":%llu,"swaptotal":%llu}",
           total, total > available ? total - available : 0, available,
           cached + buffers, swap_total > swap_free ? swap_total - swap_free : 0, swap_total);

    struct sysinfo si;
    sysinfo(&si);
    append(&p, &left, ","uptime":%ld,"procCount":%d,"memLayout":[],",
           si.uptime, process_count());

    filesystem_info(&p, &left);
    append(&p, &left, ","disksIO":{"rIO_sec":%.0f,"wIO_sec":%.0f,"ms":%.0f},",
           read_rate, write_rate, elapsed * 1000.0);
    network_info(&p, &left);
    append(&p, &left, "}");
}

static void gpu_info(char *out, size_t capacity) {
    char *p = out;
    size_t left = capacity;
    char model[512] = "";

    FILE *f = popen("lspci -nn 2>/dev/null | grep -E 'VGA compatible controller|3D controller' | head -1", "r");
    if (f) {
        fgets(model, sizeof(model), f);
        pclose(f);
    }
    model[strcspn(model, "\r\n")] = 0;

    const char *vendor = "Unknown";
    if (strstr(model, "AMD") || strstr(model, "Radeon")) vendor = "AMD";
    else if (strstr(model, "NVIDIA") || strstr(model, "GeForce")) vendor = "NVIDIA";
    else if (strstr(model, "Intel")) vendor = "Intel";

    append(&p, &left, "{"vendor":");
    json_string(&p, &left, vendor);
    append(&p, &left, ","model":");
    json_string(&p, &left, model[0] ? model : "GPU information unavailable");
    append(&p, &left, ","bus":null,"vramDetected":0,"driverVersion":"","gfx":0,"event":0,"vgt":0,"ta":0,"sx":0,"sci":0,"si":0,"sc":0,"pa":0,"db":0,"cb":0,"vramUsed":0,"vramTotal":0,"mclk":0,"sclk":0}");
}

static void send_response(int fd, int code, const char *body) {
    char header[512];
    int length = (int)strlen(body);
    const char *status = code == 200 ? "OK" : "Not Found";
    int n = snprintf(header, sizeof(header),
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: application/json\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n\r\n",
        code, status, length);
    send(fd, header, (size_t)n, 0);
    send(fd, body, (size_t)length, 0);
}

static void handle_client(int fd) {
    char request[REQ_SIZE];
    memset(request, 0, sizeof(request));
    recv(fd, request, sizeof(request) - 1, 0);

    char *body = malloc(JSON_SIZE);
    if (!body) {
        send_response(fd, 500, "{"error":"out of memory"}");
        return;
    }

    if (strncmp(request, "GET /api/system", 16) == 0) {
        system_info(body, JSON_SIZE);
        send_response(fd, 200, body);
    } else if (strncmp(request, "GET /api/processes", 18) == 0) {
        char *p = body;
        size_t left = JSON_SIZE;
        process_info(&p, &left);
        send_response(fd, 200, body);
    } else if (strncmp(request, "GET /api/gpu", 12) == 0) {
        gpu_info(body, JSON_SIZE);
        send_response(fd, 200, body);
    } else if (strncmp(request, "POST /api/kill", 14) == 0) {
        char *pid_field = strstr(request, ""pid"");
        long pid = pid_field ? strtol(strchr(pid_field, ':') + 1, NULL, 10) : 0;
        if (pid > 0 && pid != getpid() && kill((pid_t)pid, SIGKILL) == 0)
            send_response(fd, 200, "{"success":true}");
        else
            send_response(fd, 200, "{"success":false,"error":"Unable to terminate process"}");
    } else if (strncmp(request, "OPTIONS", 7) == 0) {
        send_response(fd, 200, "{}");
    } else {
        send_response(fd, 404, "{"error":"Not found"}");
    }

    free(body);
}

int main(void) {
    signal(SIGINT, stop_server);
    signal(SIGTERM, stop_server);

    int server = socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) return 1;

    int yes = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(PORT);

    if (bind(server, (struct sockaddr *)&address, sizeof(address)) < 0) {
        close(server);
        return 2;
    }
    if (listen(server, 16) < 0) {
        close(server);
        return 3;
    }

    while (running) {
        int client = accept(server, NULL, NULL);
        if (client < 0) {
            if (errno == EINTR) continue;
            break;
        }
        handle_client(client);
        close(client);
    }

    close(server);
    return 0;
}
