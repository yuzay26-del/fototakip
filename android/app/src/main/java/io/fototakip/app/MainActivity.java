package io.fototakip.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.provider.Settings;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;

/** FotoTakip arayüzünü uygulamanın içindeki sunucudan (127.0.0.1) açar. */
public class MainActivity extends Activity {
    // "localhost" bazı telefonlarda önce IPv6'ya çözülür; sunucu IPv4 dinler.
    static final String HOME = "http://127.0.0.1:" + ServerService.PORT + "/";

    private static final int REQ_FILES = 10;
    private static final int REQ_PERMS = 11;
    private static final int REQ_LOCATION = 12;

    private WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private ValueCallback<Uri[]> fileCallback;
    private Uri cameraUri;
    private GeolocationPermissions.Callback geoCallback;
    private String geoOrigin;
    private boolean loaded;
    private boolean setupShown;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setGeolocationEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(true);

        web.addJavascriptInterface(new Bridge(), "FotoTakipAndroid");
        web.setWebViewClient(new Client());
        web.setWebChromeClient(new Chrome());
        web.setDownloadListener((url, ua, disposition, mime, length) -> download(url, disposition, mime));

        showMessage("FotoTakip başlatılıyor…", "");
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_PERMS);
        }
        ServerService.start(this);
        waitForServer(0);
        askBatteryExemptionOnce();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (ServerService.state == ServerService.State.STOPPED) {
            ServerService.start(this);
            loaded = false;
            waitForServer(0);
        }
    }

    /** Sunucu portu açılana kadar bekler, sonra arayüzü yükler. */
    private void waitForServer(int tries) {
        new Thread(() -> {
            boolean up = false;
            if (ServerService.state == ServerService.State.RUNNING) {
                try (Socket sock = new Socket()) {
                    sock.connect(new InetSocketAddress("127.0.0.1", ServerService.PORT), 500);
                    up = true;
                } catch (Exception ignored) {
                }
            }
            final boolean ok = up;
            ui.post(() -> {
                if (isFinishing()) return;
                if (ok) {
                    if (!loaded) {
                        loaded = true;
                        web.loadUrl(HOME);
                    }
                    showSetupCode();
                } else if (ServerService.state == ServerService.State.ERROR) {
                    showMessage("Sunucu başlatılamadı", ServerService.lastError);
                } else if (tries > 120) {
                    showMessage("Sunucu yanıt vermiyor", "Uygulamayı kapatıp yeniden aç.");
                } else {
                    ui.postDelayed(() -> waitForServer(tries + 1), 250);
                }
            });
        }, "fototakip-wait").start();
    }

    private void showMessage(String title, String detail) {
        String html = "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
                + "<body style='font-family:sans-serif;background:#ECEFF1;color:#263238;padding:32px 20px;overflow-wrap:anywhere'>"
                + "<h2 style='color:#0A6890'>" + esc(title) + "</h2><p>" + esc(detail) + "</p></body>";
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
    }

    private static String esc(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    /** İlk kurulumda konsol yok: kurulum kodunu pencerede göster. */
    private void showSetupCode() {
        if (setupShown) return;
        new Thread(() -> {
            String code = ServerService.setupCode();
            if (code.isEmpty()) return;
            ui.post(() -> {
                if (setupShown || isFinishing()) return;
                setupShown = true;
                new AlertDialog.Builder(this)
                        .setTitle("İlk kurulum")
                        .setMessage("Yönetici hesabını açarken bu kodu gir:\n\n" + code)
                        .setPositiveButton("Kopyala", (d, w) -> {
                            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                            cm.setPrimaryClip(ClipData.newPlainText("Kurulum kodu", code));
                            Toast.makeText(this, "Kopyalandı", Toast.LENGTH_SHORT).show();
                        })
                        .setNegativeButton("Kapat", null)
                        .show();
            });
        }).start();
    }

    /** Sunucu telefonu: pil tasarrufu sunucuyu öldürmesin diye bir kez izin iste. */
    @SuppressLint("BatteryLife")
    private void askBatteryExemptionOnce() {
        SharedPreferences p = getSharedPreferences("app", MODE_PRIVATE);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (p.getBoolean("battery_asked", false) || pm.isIgnoringBatteryOptimizations(getPackageName())) return;
        p.edit().putBoolean("battery_asked", true).apply();
        new AlertDialog.Builder(this)
                .setTitle("Arka planda çalışma")
                .setMessage("Bu telefon ekibin sunucusu. Ekran kapanınca bağlantının kopmaması için "
                        + "pil optimizasyonundan muaf tutulması gerekir.")
                .setPositiveButton("İzin ver", (d, w) -> {
                    try {
                        startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                                Uri.parse("package:" + getPackageName())));
                    } catch (ActivityNotFoundException ignored) {
                    }
                })
                .setNegativeButton("Sonra", null)
                .show();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else moveTaskToBack(true); // sunucu servis olarak çalışmaya devam eder
    }

    // ---------- Bağlantılar ----------

    private class Client extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            String host = u.getHost();
            boolean local = ("http".equals(u.getScheme()) || "https".equals(u.getScheme()))
                    && ("127.0.0.1".equals(host) || "localhost".equals(host));
            if (local) return false;
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, u)); // harita, tel:, mailto:, tünel adresi
            } catch (ActivityNotFoundException e) {
                Toast.makeText(MainActivity.this, "Bu bağlantıyı açacak uygulama yok", Toast.LENGTH_SHORT).show();
            }
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            // Android WebView window.print() desteklemez; yazdırma sistemine yönlendir (PDF olarak kaydet dahil).
            view.evaluateJavascript("window.print=function(){FotoTakipAndroid.print()}", null);
        }
    }

    private class Bridge {
        @JavascriptInterface
        public void print() {
            ui.post(() -> {
                PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                pm.print("FotoTakip rapor", web.createPrintDocumentAdapter("FotoTakip rapor"), null);
            });
        }
    }

    // ---------- Kamera, galeri, konum ----------

    private class Chrome extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
            if (fileCallback != null) fileCallback.onReceiveValue(null);
            fileCallback = cb;
            Intent intent;
            if (params.isCaptureEnabled()) {
                try {
                    File dir = new File(getCacheDir(), "camera");
                    dir.mkdirs();
                    File f = File.createTempFile("foto-", ".jpg", dir);
                    cameraUri = FileProvider.getUriForFile(MainActivity.this, getPackageName() + ".files", f);
                    intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                            .putExtra(MediaStore.EXTRA_OUTPUT, cameraUri)
                            .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                } catch (Exception e) {
                    cameraUri = null;
                    intent = params.createIntent();
                }
            } else {
                cameraUri = null;
                intent = params.createIntent();
                if (params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) {
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                }
            }
            try {
                startActivityForResult(intent, REQ_FILES);
            } catch (ActivityNotFoundException e) {
                fileCallback = null;
                Toast.makeText(MainActivity.this, "Kamera ya da galeri uygulaması bulunamadı", Toast.LENGTH_SHORT).show();
                return false;
            }
            return true;
        }

        @Override
        public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                cb.invoke(origin, true, false);
                return;
            }
            geoOrigin = origin;
            geoCallback = cb;
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION);
        }
    }

    @Override
    protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req, result, data);
        if (req != REQ_FILES || fileCallback == null) return;
        Uri[] uris = null;
        if (result == RESULT_OK) {
            if (cameraUri != null) {
                uris = new Uri[]{cameraUri};
            } else if (data != null && data.getClipData() != null) {
                ClipData c = data.getClipData();
                uris = new Uri[c.getItemCount()];
                for (int i = 0; i < c.getItemCount(); i++) uris[i] = c.getItemAt(i).getUri();
            } else if (data != null && data.getData() != null) {
                uris = new Uri[]{data.getData()};
            }
        }
        fileCallback.onReceiveValue(uris);
        fileCallback = null;
        cameraUri = null;
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] results) {
        super.onRequestPermissionsResult(req, perms, results);
        if (req == REQ_LOCATION && geoCallback != null) {
            boolean ok = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
            geoCallback.invoke(geoOrigin, ok, false);
            geoCallback = null;
        }
    }

    // ---------- İndirme (yedek zip) ----------

    private void download(String url, String disposition, String mime) {
        String name = URLUtil.guessFileName(url, disposition, mime);
        String cookie = CookieManager.getInstance().getCookie(url);
        Toast.makeText(this, "İndiriliyor: " + name, Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            String msg;
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                if (cookie != null) c.setRequestProperty("Cookie", cookie);
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                try (InputStream in = c.getInputStream()) {
                    msg = save(in, name, mime);
                }
            } catch (Exception e) {
                msg = "İndirilemedi: " + e.getMessage();
            }
            final String m = msg;
            ui.post(() -> Toast.makeText(this, m, Toast.LENGTH_LONG).show());
        }, "fototakip-download").start();
    }

    private String save(InputStream in, String name, String mime) throws Exception {
        OutputStream out;
        String where;
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime == null ? "application/octet-stream" : mime);
            Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (u == null) throw new Exception("İndirilenler klasörü açılamadı");
            out = getContentResolver().openOutputStream(u);
            where = "İndirilenler klasörüne kaydedildi: " + name;
        } else {
            File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            File f = new File(dir, name);
            out = new FileOutputStream(f);
            where = "Kaydedildi: " + f.getAbsolutePath();
        }
        try (OutputStream o = out) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) > 0) o.write(buf, 0, n);
        }
        return where;
    }
}
