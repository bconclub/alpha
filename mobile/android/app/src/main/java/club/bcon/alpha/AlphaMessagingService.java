package club.bcon.alpha;

import android.app.PendingIntent;
import android.content.Intent;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

/** Shows Alpha pushes while the app is open (Android only auto-shows them in the background). */
public class AlphaMessagingService extends FirebaseMessagingService {
    @Override
    public void onMessageReceived(RemoteMessage msg) {
        RemoteMessage.Notification n = msg.getNotification();
        if (n == null) return;
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, MainActivity.CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(n.getTitle())
            .setContentText(n.getBody())
            .setStyle(new NotificationCompat.BigTextStyle().bigText(n.getBody()))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pi);
        try {
            NotificationManagerCompat.from(this).notify((int) System.currentTimeMillis(), b.build());
        } catch (SecurityException e) {
            // notification permission not granted
        }
    }
}
