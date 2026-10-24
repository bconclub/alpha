package club.bcon.alpha;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;

public class MainActivity extends BridgeActivity {
    static final String CHANNEL_ID = "alpha_trades";
    static final String TOPIC = "alpha";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createChannel();
        askNotificationPermission();
        subscribe();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "Trades & daily P&L", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("New trades, closed trades and the daily P&L from Alpha");
            getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    private void askNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
            && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1001);
        }
    }

    private void subscribe() {
        // Builds without google-services.json have no Firebase app: skip quietly.
        if (FirebaseApp.getApps(this).isEmpty()) {
            Log.w("Alpha", "Firebase not configured; push disabled");
            return;
        }
        FirebaseMessaging.getInstance().subscribeToTopic(TOPIC)
            .addOnCompleteListener(t -> Log.i("Alpha", "Topic subscribe: " + t.isSuccessful()));
    }
}
