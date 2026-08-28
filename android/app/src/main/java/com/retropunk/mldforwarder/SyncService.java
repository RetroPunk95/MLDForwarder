package com.retropunk.mldforwarder;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SyncService extends Service {
    static final String EXTRA_MODE = "mode";
    static final String EXTRA_CONFIG = "config";
    static final String ACTION_LOG = "com.retropunk.mldforwarder.LOG";
    static final String EXTRA_LOG = "log";

    private static final int NOTIFICATION_ID = 83;
    private static final String CHANNEL_ID = "mld_sync";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean running = new AtomicBoolean(false);

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String mode = intent == null ? "normal" : intent.getStringExtra(EXTRA_MODE);
        String config = intent == null ? "{}" : intent.getStringExtra(EXTRA_CONFIG);
        if (mode == null) mode = "normal";
        if (config == null) config = "{}";

        startForeground(NOTIFICATION_ID, buildNotification(mode));

        if (!running.compareAndSet(false, true)) {
            emit("Já existe uma sincronização em execução.");
            return START_NOT_STICKY;
        }

        final String selectedMode = mode;
        final String selectedConfig = config;

        executor.execute(() -> {
            try {
                emit("Motor Android iniciado em modo " + selectedMode + ".");
                String method = "retro".equals(selectedMode) ? "run_retro" : "run_normal";
                PythonBridge.call(
                        getApplicationContext(),
                        method,
                        selectedConfig,
                        new LogListener()
                );
            } catch (Throwable error) {
                emit("Falha no motor: " + error.getMessage());
            } finally {
                running.set(false);
                emit("Sincronização encerrada.");
                stopSelf();
            }
        });

        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        PythonBridge.requestStop(getApplicationContext());
        executor.shutdownNow();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onTimeout(int startId, int fgsType) {
        emit("O Android encerrou o serviço por limite de execução.");
        PythonBridge.requestStop(getApplicationContext());
        stopSelf(startId);
    }

    private Notification buildNotification(String mode) {
        Intent openIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                openIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        String title = "retro".equals(mode)
                ? "Sincronização retroativa ativa"
                : "Sincronização normal ativa";

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setSmallIcon(android.R.drawable.stat_sys_upload)
                .setContentTitle(title)
                .setContentText("Toque para abrir o MLDForwarder")
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.notification_channel),
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Mantém a sincronização visível enquanto está ativa.");
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(channel);
        }
    }

    private void emit(String message) {
        Intent event = new Intent(ACTION_LOG);
        event.setPackage(getPackageName());
        event.putExtra(EXTRA_LOG, message);
        sendBroadcast(event);
    }

    public final class LogListener {
        public void onLog(String message) {
            emit(message);
        }
    }
}
