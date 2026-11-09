import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;

/**
 * Build a minimal but VALID class file:
 *   public class &lt;name&gt; { public &lt;init&gt;() { super(); } }
 *
 * Constant pool (1-based):
 *   #1 Utf8        <name>
 *   #2 Class       #1
 *   #3 Utf8        java/lang/Object
 *   #4 Class       #3
 *   #5 Utf8        <init>
 *   #6 Utf8        ()V
 *   #7 Utf8        Code
 *   #8 NameAndType #5:#6
 *   #9 Methodref   #4.#8     &lt;-- required: invokespecial needs a Methodref, not a Class entry
 */
public final class ClassGenerator {
    private ClassGenerator() {}

    public static byte[] minimalClass(String name) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);

        out.writeInt(0xCAFEBABE);
        out.writeShort(0);          // minor
        out.writeShort(65);         // major = Java 21

        out.writeShort(10);         // constant_pool_count = so entry + 1
        out.writeByte(1); out.writeUTF(name);                 // #1
        out.writeByte(7); out.writeShort(1);                  // #2 Class -> #1
        out.writeByte(1); out.writeUTF("java/lang/Object");   // #3
        out.writeByte(7); out.writeShort(3);                  // #4 Class -> #3
        out.writeByte(1); out.writeUTF("<init>");             // #5
        out.writeByte(1); out.writeUTF("()V");                // #6
        out.writeByte(1); out.writeUTF("Code");               // #7
        out.writeByte(12); out.writeShort(5); out.writeShort(6); // #8 NameAndType
        out.writeByte(10); out.writeShort(4); out.writeShort(8); // #9 Methodref -> #4.#8

        out.writeShort(0x0021);     // ACC_PUBLIC | ACC_SUPER
        out.writeShort(2);          // this_class  = #2
        out.writeShort(4);          // super_class = #4
        out.writeShort(0);          // interfaces_count
        out.writeShort(0);          // fields_count
        out.writeShort(1);          // methods_count

        out.writeShort(0x0001);     // ACC_PUBLIC
        out.writeShort(5);          // name        = #5
        out.writeShort(6);          // descriptor  = #6
        out.writeShort(1);          // attributes_count
        out.writeShort(7);          // "Code"
        out.writeInt(17);           // attribute_length
        out.writeShort(1);          // max_stack
        out.writeShort(1);          // max_locals
        out.writeInt(5);            // code_length
        out.writeByte(0x2A);        // aload_0
        out.writeByte(0xB7); out.writeShort(9);  // invokespecial #9
        out.writeByte(0xB1);        // return
        out.writeShort(0);          // exception_table_length
        out.writeShort(0);          // code attributes

        out.writeShort(0);          // class attributes_count
        out.flush();
        return bytes.toByteArray();
    }
}
