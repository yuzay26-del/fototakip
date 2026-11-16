package io.fototakip.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.ServiceInfo;
import android.content.res.AssetManager;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;

/**
 * FotoTakip sunucusunu (Python) uygulamanın içinde çalıştırır. Ön plan servisi olduğu için
 * ekran kapanınca ya da uygulama kapatılınca Android sunucuyu durdurmaz.
 */
public class ServerService extends Service {
    public static final int PORT = 8080;
    public static final String ACTION_STOP = "io.fototakip.app.STOP";

    public enum State { STOPPED, STARTING, RUNNING, ERROR }

    static volatile State state = State.STOPPED;
    static volatile String lastError = "";
    static volatile String note = "";

    private static final String CHANNEL = "server";
    private static final int NOTIF_ID = 1;

    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;

    public static void start(Context ctx) {
        Intent i = new Intent(ctx, ServerService.class);
        if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i);
        else ctx.startService(i);
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }
        goForeground("Başlatılıyor…");
        if (state == State.STOPPED || state == State.ERROR) {
            state = State.STARTING;
            lastError = "";
            new Thread(this::boot, "fototakip-boot").start();
        }
        return START_STICKY;
    }

    private void boot() {
        try {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
            File web = syncWebAssets();
            String cloudflared = getApplicationInfo().nativeLibraryDir + "/libcloudflared.so";
            PyObject r = module().callAttr("start", getFilesDir().getAbsolutePath(),
                    getCacheDir().getAbsolutePath(), web.getAbsolutePath(), cloudflared, PORT);
            note = r == null ? "" : r.toString();
            acquireLocks();
            state = State.RUNNING;
            List<PyObject> urls = module().callAttr("lan_urls").asList();
            goForeground(urls.isEmpty() ? "Bu telefonda açık" : "Ekip için: " + urls.get(0).toString());
        } catch (Throwable t) {
            String msg = String.valueOf(t.getMessage());
            if (msg.contains("Address already in use") || msg.contains("Errno 98")) {
                msg = PORT + " numaralı port kullanımda. Termux'ta FotoTakip açıksa önce onu durdur (Ctrl+C), sonra uygulamayı yeniden aç.";
            }
            lastError = msg;
            state = State.ERROR;
            goForeground("Başlatılamadı");
        }
    }

    static PyObject module() {
        return Python.getInstance().getModule("fototakip_android");
    }

    /** Kurulum kodu (ilk yönetici hesabı açılana kadar), yoksa "". */
    static String setupCode() {
        if (state != State.RUNNING) return "";
        try {
            return module().callAttr("setup_code").toString();
        } catch (Throwable t) {
            return "";
        }
    }

    /** web/ klasörünü APK'dan diske açar; yalnızca uygulama güncellendiğinde yeniden yazar. */
    private File syncWebAssets() throws Exception {
        File dir = new File(getFilesDir(), "web");
        File stamp = new File(getFilesDir(), "web.stamp");
        PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
        String want = pi.lastUpdateTime + ":" + pi.versionName;
        if (dir.isDirectory() && stamp.exists()
                && want.equals(new String(Files.readAllBytes(stamp.toPath()), StandardCharsets.UTF_8))) {
            return dir;
        }
        deleteTree(dir);
        copyAssets(getAssets(), "web", dir);
        Files.write(stamp.toPath(), want.getBytes(StandardCharsets.UTF_8));
        return dir;
    }

    private static void copyAssets(AssetManager am, String path, File dest) throws IOException {
        String[] children = am.list(path);
        if (children == null || children.length == 0) {
            dest.getParentFile().mkdirs();
            try (InputStream in = am.open(path); OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[64 * 1024];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            }
            return;
        }
        dest.mkdirs();
        for (String c : children) copyAssets(am, path + "/" + c, new File(dest, c));
    }

    private static void deleteTree(File f) {
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) deleteTree(k);
        f.delete();
    }

    private void acquireLocks() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "FotoTakip:server");
        wakeLock.acquire();
        WifiManager wm = (WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
        if (wm != null) {
            int mode = Build.VERSION.SDK_INT >= 29 ? WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                    : WifiManager.WIFI_MODE_FULL_HIGH_PERF;
            wifiLock = wm.createWifiLock(mode, "FotoTakip:server");
            wifiLock.acquire();
        }
    }

    private void goForeground(String text) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Sunucu", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("FotoTakip sunucusu çalışırken görünür");
            nm.createNotificationChannel(ch);
        }
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, ServerService.class).setAction(ACTION_STOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("FotoTakip sunucusu")
                .setContentText(text)
                .setContentIntent(open)
                .setOngoing(true)
                .addAction(new Notification.Action.Builder(null, "Durdur", stop).build())
                .build();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIF_ID, n);
        }
    }

    @Override
    public void onDestroy() {
        try {
            if (Python.isStarted()) module().callAttr("stop");
        } catch (Throwable ignored) {
        }
        state = State.STOPPED;
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        super.onDestroy();
    }
}
