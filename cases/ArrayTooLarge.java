/**
 * Case 5 — one single allocation larger than the VM can ever satisfy.
 * The heap is almost empty: this is NOT a leak, and raising -Xmx changes nothing.
 */
public class ArrayTooLarge {
    public static void main(String[] args) {
        System.out.println("progress=before_allocation");
        System.out.println("requested_bytes=" + Integer.MAX_VALUE);
        byte[] a = new byte[Integer.MAX_VALUE];   // bigger than the max array size the VM allows
        System.out.println("progress=never_reached length=" + a.length);
    }
}
