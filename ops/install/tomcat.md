# Install on Tomcat (WAR on a host)

## 1. Put the flags in `setenv.sh`, never in `catalina.sh`

`$CATALINA_BASE/bin/setenv.sh`:

```bash
export JAVA_OPTS="$JAVA_OPTS \
  -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/tomcat-dumps \
  -XX:+ExitOnOutOfMemoryError -XX:NativeMemoryTracking=summary \
  -Xlog:gc*:file=/var/log/tomcat-dumps/gc.log:time,uptime,level,tags:filecount=5,filesize=20m"
```

`catalina.sh` is overwritten by every Tomcat upgrade; `setenv.sh` is not. This is the single most common
way the flags disappear between releases.

```bash
sudo mkdir -p /var/log/tomcat-dumps && sudo chown tomcat: /var/log/tomcat-dumps
sudo -u tomcat bash ops/guard.sh tomcat /var/log/tomcat-dumps      # guard=armed
sudo systemctl restart tomcat
```

## 2. Size the limit for the whole process, not the heap

Tomcat adds Metaspace, code cache, thread stacks, direct buffers and the **class loader per webapp**.
A common layout for `-Xmx1g`:

```
-Xmx1g  -XX:MaxMetaspaceSize=256m  -Xss1m   plus ~200-300m native  ->  container/VM needs ~1.6-1.8g
```

If the JVM is killed at 137 while the heap never throws, the ceiling is too low — see the
`container_kill` row in [`docs/ATTRIBUTION.md`](../../docs/ATTRIBUTION.md).

## 3. Snapshots

Per-minute cost on a 1 GB heap is small, but do not run it every 10 seconds on a large heap:
`jcmd GC.class_histogram` walks the heap and takes a short safepoint.

```bash
*/5 * * * * pid=$(pgrep -f 'org.apache.catalina.startup.Bootstrap' | head -1); \
             [ -n "$pid" ] && timeout 240 bash /opt/oom-lab/ops/watch.sh "$pid" 240 >>/var/log/tomcat-dumps/watch.log 2>&1
```

## 4. Where the evidence is, after a webapp OOM

```
/var/log/tomcat-dumps/java_pid<PID>.hprof     heap dump (only if the JVM threw, not if it was killed)
/var/log/tomcat-dumps/gc.log                  rolling GC log, 5 files x 20 MB
/var/log/tomcat-dumps/hs_err_pid<PID>.log     native crash (metaspace/malloc), not a Java OOME
$CATALINA_BASE/logs/catalina.out              the OutOfMemoryError line with its detail message
```

Then:

```bash
python3 ops/classify.py <bundle-dir>     # kind + 4 ordered checks + attribution
python3 ops/store.py archive <bundle-dir>
```

**The trap:** a Metaspace OOM in Tomcat is usually a webapp that is redeployed without its class loader
being released. `-XX:MaxMetaspaceSize` only delays it; the fix is in the webapp lifecycle.
