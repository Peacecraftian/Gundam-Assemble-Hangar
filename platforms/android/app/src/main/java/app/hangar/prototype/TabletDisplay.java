package app.hangar.prototype;

import android.app.Activity;
import android.content.Context;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

final class TabletDisplay {
    private TabletDisplay() {}
    static boolean fullscreen(Activity app) {
        return app.getSharedPreferences("display",Context.MODE_PRIVATE).getBoolean("fullscreen",false);
    }
    static String label(Activity app) { return fullscreen(app) ? "Exit fullscreen" : "Fullscreen"; }
    static void toggle(Activity app) {
        app.getSharedPreferences("display",Context.MODE_PRIVATE).edit().putBoolean("fullscreen",!fullscreen(app)).apply();
        apply(app);
    }
    static void apply(Activity app) {
        apply(app,app.getWindow());
    }
    static void apply(Activity app,android.view.Window window) {
        boolean hide=fullscreen(app);
        if (Build.VERSION.SDK_INT>=30) {
            WindowInsetsController c=window.getInsetsController();
            if (c==null) return;
            c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            if (hide) c.hide(WindowInsets.Type.systemBars()); else c.show(WindowInsets.Type.systemBars());
        } else {
            window.getDecorView().setSystemUiVisibility(hide ? View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY : View.SYSTEM_UI_FLAG_VISIBLE);
        }
    }
}
