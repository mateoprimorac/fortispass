# libsodium / JNA
-keep class com.goterl.** { *; }
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.** { public *; }

# ML Kit
-keep class com.google.mlkit.** { *; }

# App models (keep for reflection/serialization)
-keep class com.zkpm.** { *; }

# Standard Android rules
-keepattributes *Annotation*
-keepattributes SourceFile,LineNumberTable
-dontwarn java.awt.**
