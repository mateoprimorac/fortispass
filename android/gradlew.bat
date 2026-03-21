@echo off
set APP_HOME=%~dp0
"%JAVA_HOME%\bin\java.exe" -classpath "%APP_HOME%\gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain %*
