# Install in Docker (single container)

## 1. Bind-mount the dump directory

```bash
docker run -d --name api --memory=1536m --memory-swap=1536m \
  -v /data/java-dumps:/dumps \
  -e JAVA_OPTS="-Xmx1g -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps \
     -XX:+ExitOnOutOfMemoryError -XX:NativeMemoryTracking=summary" \
  registry.example.com/api:1.2.3
```

Without `-v`, the dump is written into the container filesystem and disappears with the container.
With `--rm`, it disappears even faster.

## 2. Read the kill, not the logs

```bash
docker inspect api --format 'OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}'
docker inspect api --format 'Memory={{.HostConfig.Memory}} PidsLimit={{.HostConfig.PidsLimit}}'
dmesg -T | grep -i 'killed process' | tail -5
```

`ExitCode 137` + `OOMKilled=true` means the kernel killed it: no dump exists and none can be created.

## 3. Verify

```bash
bash ops/guard.sh docker /data/java-dumps     # checks writability, tmpfs, free space, oom_kill counter
```

**The trap:** `--memory` smaller than `Xmx + off-heap + stacks` kills the container long before Java
throws, and the JVM never gets the chance to write a dump. Size the limit for the process, not the heap.
