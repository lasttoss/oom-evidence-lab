/**
 * Case 6 — cannot create a thread (native thread OOM).
 * A thread stack is off-heap memory committed at creation: the heap can be mostly free
 * and the process still dies, because threads x -Xss is memory the container must supply.
 */
public class NativeThreadOOM {
    public static void main(String[] args) throws Exception {
        int i = 0;
        try {
            while (true) {
                Thread t = new Thread(() -> {
                    try { Thread.sleep(600_000); } catch (InterruptedException ignored) { }
                });
                t.setDaemon(true);   // daemon: the JVM must not wait 10 minutes for these to finish
                t.start();
                i++;
                if (i % 50 == 0) System.out.println("threads_created=" + i);
            }
        } finally {
            System.out.println("threads_created=" + i);
        }
    }
}
