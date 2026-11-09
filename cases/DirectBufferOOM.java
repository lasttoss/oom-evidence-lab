import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;

/**
 * Case 2 — OOM in the direct buffer region (off-heap, outside GC control).
 * The heap stays clean; -XX:MaxDirectMemorySize is what gets exceeded.
 */
public class DirectBufferOOM {
    public static void main(String[] args) {
        System.out.println("pid=" + ProcessHandle.current().pid());
        List<ByteBuffer> keep = new ArrayList<>();
        for (int i = 1; ; i++) {
            keep.add(ByteBuffer.allocateDirect(1024 * 1024));
            if (i % 8 == 0) {
                System.out.println("direct_mb=" + i);
                System.out.flush();
            }
        }
    }
}
