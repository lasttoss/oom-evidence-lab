import java.util.ArrayList;
import java.util.List;

/**
 * Case 4 — killed by the KERNEL (cgroup), not by a JVM OutOfMemoryError.
 * Runs in a container whose --memory is below real demand: exit code 137, OOMKilled=true.
 */
public class ContainerKill {
    public static void main(String[] args) throws Exception {
        System.out.println("pid=" + ProcessHandle.current().pid());
        List<byte[]> keep = new ArrayList<>();
        for (int i = 1; ; i++) {
            keep.add(new byte[8 * 1024 * 1024]);
            if (i % 4 == 0) {
                System.out.println("rss_target_mb=" + (long) i * 8);
                System.out.flush();
            }
            Thread.sleep(50);
        }
    }
}
