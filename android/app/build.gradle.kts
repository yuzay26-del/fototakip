import java.io.FileInputStream
import java.net.URI
import java.security.MessageDigest
import java.util.Properties
import org.tukaani.xz.XZInputStream

buildscript {
    repositories { mavenCentral() }
    dependencies {
        classpath("org.tukaani:xz:1.10")
    }
}

plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// Depo kökü: Python paketi (fototakip/) ve istemci (web/) buradan alınır; kopya tutulmaz.
val repoRoot: File = rootProject.projectDir.parentFile

// Sürüm tek yerden: fototakip/__init__.py
val appVersion: String = Regex("__version__\\s*=\\s*\"([^\"]+)\"")
    .find(File(repoRoot, "fototakip/__init__.py").readText())!!.groupValues[1]
val appVersionCode: Int = appVersion.split(".").map { it.toInt() }.let { (a, b, c) -> a * 10000 + b * 100 + c }

// İmza: android/keystore.properties varsa onunla (güncellemeler için hep aynı anahtar şart), yoksa debug.
val keystoreProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) FileInputStream(f).use { load(it) }
}

android {
    namespace = "io.fototakip.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.fototakip.app"
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersion
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    signingConfigs {
        if (keystoreProps.isNotEmpty()) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // cloudflared "lib…so" adıyla gelir: Android yalnızca yerel kütüphane klasöründen program çalıştırmaya izin verir.
    packaging { jniLibs { useLegacyPackaging = true } }

    sourceSets {
        getByName("main") {
            assets.srcDir(layout.buildDirectory.dir("generated/fototakip/assets"))
            jniLibs.srcDir(layout.buildDirectory.dir("generated/fototakip/jniLibs"))
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        pip {
            install("pillow")   // isteğe bağlı ama fotoğrafları döndürüp küçültmek için gerekli
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir(repoRoot)
            include("fototakip/**/*.py", "fototakip_android.py")
        }
    }
}

/** .deb = ar arşivi; içindeki data.tar.xz'ten adı [suffix] ile biten dosyayı döndürür. */
fun extractFromDeb(deb: ByteArray, suffix: String): ByteArray? {
    var pos = 8 // "!<arch>\n"
    var tarXz: ByteArray? = null
    while (pos + 60 <= deb.size) {
        val name = String(deb, pos, 16, Charsets.US_ASCII).trim()
        val size = String(deb, pos + 48, 10, Charsets.US_ASCII).trim().toInt()
        if (name.startsWith("data.tar.xz")) { tarXz = deb.copyOfRange(pos + 60, pos + 60 + size); break }
        pos += 60 + size + (size % 2)
    }
    val tar = XZInputStream(tarXz?.inputStream() ?: return null).readBytes()
    pos = 0
    while (pos + 512 <= tar.size) {
        val rawName = String(tar, pos, 100, Charsets.UTF_8).substringBefore('\u0000')
        if (rawName.isEmpty()) break
        val prefix = String(tar, pos + 345, 155, Charsets.UTF_8).substringBefore('\u0000')
        val fullName = if (prefix.isEmpty()) rawName else "$prefix/$rawName"
        val size = String(tar, pos + 124, 12, Charsets.US_ASCII).trim('\u0000', ' ').toLong(8).toInt()
        if (fullName.endsWith(suffix)) return tar.copyOfRange(pos + 512, pos + 512 + size)
        pos += 512 + ((size + 511) / 512) * 512
    }
    return null
}

val copyWeb by tasks.registering(Sync::class) {
    from(File(repoRoot, "web"))
    into(layout.buildDirectory.dir("generated/fototakip/assets/web"))
}

val cfVersion = providers.gradleProperty("fototakip.cloudflared.version").get()
val cfSha = providers.gradleProperty("fototakip.cloudflared.sha256").get()

val fetchCloudflared by tasks.registering {
    val out = layout.buildDirectory.file("generated/fototakip/jniLibs/arm64-v8a/libcloudflared.so")
    val cache = rootProject.file(".cache/cloudflared_${cfVersion}_aarch64.deb")
    inputs.property("version", cfVersion)
    inputs.property("sha256", cfSha)
    outputs.file(out)
    doLast {
        if (!cache.exists()) {
            cache.parentFile.mkdirs()
            val url = "https://packages.termux.dev/apt/termux-main/pool/main/c/cloudflared/cloudflared_${cfVersion}_aarch64.deb"
            logger.lifecycle("cloudflared indiriliyor: $url")
            URI(url).toURL().openStream().use { input -> cache.outputStream().use { input.copyTo(it) } }
        }
        val digest = MessageDigest.getInstance("SHA-256").digest(cache.readBytes()).joinToString("") { "%02x".format(it) }
        if (digest != cfSha) {
            cache.delete()
            throw GradleException("cloudflared paketinin SHA-256 değeri tutmuyor ($digest). gradle.properties'i kontrol et.")
        }
        val bin = extractFromDeb(cache.readBytes(), "/usr/bin/cloudflared")
            ?: throw GradleException("cloudflared paketin içinde bulunamadı.")
        out.get().asFile.apply { parentFile.mkdirs(); writeBytes(bin) }
    }
}

tasks.named("preBuild") { dependsOn(copyWeb, fetchCloudflared) }

dependencies {
    implementation("androidx.core:core:1.13.1")
    implementation("androidx.webkit:webkit:1.12.1")
}
