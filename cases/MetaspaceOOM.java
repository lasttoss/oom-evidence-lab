import java.util.ArrayList;
import java.util.List;

/**
 * Case 3 — Metaspace OOM: generate classes in many distinct ClassLoaders and KEEP
 * a strong reference to each one (simulating a hot-reload that never closes its loader).
 */
public class MetaspaceOOM {
    public static void main(String[] args) throws Exception {
        System.out.println("pid=" + ProcessHandle.current().pid());
        List<ClassLoader> keep = new ArrayList<>();
        byte[] bytecode = ClassGenerator.minimalClass("Generated");

        for (int i = 1; ; i++) {
            ClassLoader loader = new ClassLoader(MetaspaceOOM.class.getClassLoader()) {
                @Override
                protected Class<?> findClass(String name) {
                    return defineClass(name, bytecode, 0, bytecode.length);
                }
            };
            Class<?> c = loader.loadClass("Generated");
            c.getDeclaredConstructor().newInstance();   // required: prove the class actually works
            keep.add(loader);                          // required: retain the loader => metaspace is never freed
            if (i % 2000 == 0) {
                System.out.println("classes_defined=" + i);
                System.out.flush();
            }
        }
    }
}
