import java.util.ArrayList;
import java.util.List;

/**
 * Case 1 — heap OOM caused by objects RETAINED by a static field.
 * Nothing is "wrong" on any single line: it is just a list with no ceiling.
 */
public class HeapLeak {
    static final List<byte[]> RETAINED = new ArrayList<>();
    static final int STEP_MB = 8;

    public static void main(String[] args) throws Exception {
        System.out.println("pid=" + ProcessHandle.current().pid());
        for (int i = 1; ; i++) {
            RETAINED.add(new byte[STEP_MB * 1024 * 1024]);
            if (i % 4 == 0) {
                System.out.println("retained_mb=" + (long) i * STEP_MB);
                System.out.flush();
            }
            Thread.sleep(400);
        }
    }
}
