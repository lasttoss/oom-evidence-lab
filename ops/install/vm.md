# Install on a VM (systemd)

## 1. Copy and check

```bash
sudo mkdir -p /opt/oom-lab && sudo cp -r ops /opt/oom-lab/
sudo mkdir -p /var/log/java-dumps && sudo chown <jvm-user>: /var/log/java-dumps
sudo -u <jvm-user> bash /opt/oom-lab/ops/guard.sh vm /var/log/java-dumps    # must print guard=armed
```

## 2. Flags — in the unit, never in a shell profile

`/etc/systemd/system/<service>.service`:

```ini
[Service]
Environment="JAVA_OPTS=-Xmx1g \
 -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/java-dumps \
 -XX:+ExitOnOutOfMemoryError -XX:NativeMemoryTracking=summary \
 -Xlog:gc*:file=/var/log/java-dumps/gc.log:time,uptime,level,tags:filecount=5,filesize=20m"
ExecStart=/usr/bin/java $JAVA_OPTS -jar /opt/<service>/app.jar
```

```bash
sudo systemctl daemon-reload && sudo systemctl restart <service>
```

## 3. Snapshots — a systemd timer, not a loop nobody owns

`/etc/systemd/system/oom-watch.service`:

```ini
[Service]
Type=oneshot
User=<jvm-user>
ExecStart=/bin/bash -c 'pid=$(pgrep -f app.jar | head -1); [ -n "$pid" ] && timeout 300 bash /opt/oom-lab/ops/watch.sh "$pid" 300'
```

`oom-watch.timer`: `OnUnitActiveSec=5min`, `OnBootSec=2min`. Then `systemctl enable --now oom-watch.timer`.

## 4. Verify with a real event, not with faith

```bash
# a 30-second controlled OOM in a scratch JVM — proves the whole path end to end
java -Xmx64m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/java-dumps \
     -cp /opt/oom-lab/lab/cases ... 2>/dev/null || true
ls -lt /var/log/java-dumps | head -3
python3 /opt/oom-lab/ops/classify.py /var/log/java-dumps    # if the bundle dir matches a case layout
```

## 5. Fetch and keep

```bash
python3 /opt/oom-lab/ops/store.py archive <case-dir>    # bundle + index line
python3 /opt/oom-lab/ops/store.py prune --dumps-days 30 # text stays forever, dumps expire
```

**The trap:** the dump is written by the JVM user, into a directory root created — `Permission denied` is
silent, the process still dies. That is why step 1 ends with `guard.sh`, which checks writability as the
JVM user.
