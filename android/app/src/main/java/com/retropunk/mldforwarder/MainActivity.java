package com.retropunk.mldforwarder;

import android.Manifest;
import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String PREFS = "mld_alpha";
    private static final int NOTIFICATION_PERMISSION_REQUEST = 83;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            appendLog(intent.getStringExtra(SyncService.EXTRA_LOG));
        }
    };

    private EditText apiIdInput;
    private EditText apiHashInput;
    private EditText phoneInput;
    private EditText codeInput;
    private EditText passwordInput;
    private EditText routeNameInput;
    private EditText sourceInput;
    private EditText sourceTopicInput;
    private EditText targetInput;
    private EditText targetTopicInput;
    private EditText retroLimitInput;
    private EditText retroStartIdInput;
    private TextView logText;
    private String phoneCodeHash = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        bindViews();
        restoreFields();
        bindActions();
        requestNotificationPermissionIfNeeded();
    }

    @Override
    protected void onStart() {
        super.onStart();
        IntentFilter filter = new IntentFilter(SyncService.ACTION_LOG);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(logReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(logReceiver, filter);
        }
    }

    @Override
    protected void onStop() {
        unregisterReceiver(logReceiver);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void bindViews() {
        apiIdInput = findViewById(R.id.apiIdInput);
        apiHashInput = findViewById(R.id.apiHashInput);
        phoneInput = findViewById(R.id.phoneInput);
        codeInput = findViewById(R.id.codeInput);
        passwordInput = findViewById(R.id.passwordInput);
        routeNameInput = findViewById(R.id.routeNameInput);
        sourceInput = findViewById(R.id.sourceInput);
        sourceTopicInput = findViewById(R.id.sourceTopicInput);
        targetInput = findViewById(R.id.targetInput);
        targetTopicInput = findViewById(R.id.targetTopicInput);
        retroLimitInput = findViewById(R.id.retroLimitInput);
        retroStartIdInput = findViewById(R.id.retroStartIdInput);
        logText = findViewById(R.id.logText);
        passwordInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    }

    private void bindActions() {
        findViewById(R.id.sendCodeButton).setOnClickListener(v -> sendCode());
        findViewById(R.id.checkSessionButton).setOnClickListener(v -> checkSession());
        findViewById(R.id.confirmLoginButton).setOnClickListener(v -> confirmLogin());
        findViewById(R.id.listDialogsButton).setOnClickListener(v -> listDialogs());
        findViewById(R.id.listTopicsButton).setOnClickListener(v -> listTopics());
        findViewById(R.id.startNormalButton).setOnClickListener(v -> startSync("normal"));
        findViewById(R.id.startRetroButton).setOnClickListener(v -> startSync("retro"));
        findViewById(R.id.stopButton).setOnClickListener(v -> stopSync());
    }

    private void sendCode() {
        if (!validateAccount()) return;
        saveFields();
        appendLog("Solicitando código ao Telegram...");
        runPython("send_code", result -> {
            phoneCodeHash = result.optString("phone_code_hash", "");
            getSharedPreferences(PREFS, MODE_PRIVATE)
                    .edit()
                    .putString("phone_code_hash", phoneCodeHash)
                    .apply();
            appendLog(result.optString("message", result.optString("error", "Resposta recebida.")));
        }, accountJson().toString(), text(phoneInput));
    }

    private void checkSession() {
        if (!validateAccount()) return;
        saveFields();
        appendLog("Verificando sessão...");
        runPython("check_session", result ->
                appendLog(result.optString("message", result.optString("error", "Verificação concluída."))),
                accountJson().toString()
        );
    }

    private void confirmLogin() {
        if (!validateAccount()) return;
        if (text(codeInput).isEmpty() || phoneCodeHash.isEmpty()) {
            toast("Solicite o código antes de confirmar.");
            return;
        }
        appendLog("Confirmando código...");
        runPython("confirm_code", result -> {
            if (result.optBoolean("need_password", false)) {
                String password = text(passwordInput);
                if (password.isEmpty()) {
                    appendLog("A conta exige a senha de verificação em duas etapas.");
                    return;
                }
                runPython("confirm_password", passwordResult ->
                                {
                                    if (passwordResult.optBoolean("authorized", false)) clearPhoneCodeHash();
                                    appendLog(passwordResult.optString("message", passwordResult.optString("error", "Senha processada.")));
                                },
                        accountJson().toString(), password
                );
            } else {
                if (result.optBoolean("authorized", false)) clearPhoneCodeHash();
                appendLog(result.optString("message", result.optString("error", "Código processado.")));
            }
        }, accountJson().toString(), text(phoneInput), text(codeInput), phoneCodeHash);
    }

    private void listDialogs() {
        if (!validateAccount()) return;
        appendLog("Carregando canais e grupos...");
        runPython("list_dialogs", result -> {
            if (!result.optBoolean("ok", false)) {
                appendLog(result.optString("error", "Não foi possível listar os chats."));
                return;
            }
            appendLog(result.optString("formatted", "Nenhum canal ou grupo encontrado."));
        }, accountJson().toString());
    }

    private void listTopics() {
        if (!validateAccount()) return;
        if (text(sourceInput).isEmpty()) {
            toast("Informe o grupo de origem.");
            return;
        }
        appendLog("Carregando tópicos da origem...");
        runPython("list_topics", result -> {
            if (!result.optBoolean("ok", false)) {
                appendLog(result.optString("error", "Não foi possível listar os tópicos."));
                return;
            }
            appendLog(result.optString("formatted", "Nenhum tópico encontrado."));
        }, accountJson().toString(), text(sourceInput));
    }

    private void startSync(String mode) {
        if (!validateAccount() || !validateRoute()) return;
        saveFields();
        try {
            JSONObject config = accountJson();
            config.put("files_dir", getFilesDir().getAbsolutePath());
            config.put("route_name", text(routeNameInput));
            config.put("source", text(sourceInput));
            putOptionalInt(config, "source_topic", text(sourceTopicInput));
            config.put("target", text(targetInput));
            putOptionalInt(config, "target_topic", text(targetTopicInput));
            config.put("interval", 5);
            config.put("batch_size", 100);
            config.put("retro_limit", positiveInt(text(retroLimitInput), 100));
            config.put("retro_start_id", nonNegativeInt(text(retroStartIdInput), 0));

            Intent service = new Intent(this, SyncService.class);
            service.putExtra(SyncService.EXTRA_MODE, mode);
            service.putExtra(SyncService.EXTRA_CONFIG, config.toString());
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(service);
            } else {
                startService(service);
            }
            appendLog("Solicitação enviada ao serviço: " + mode + ".");
        } catch (JSONException | NumberFormatException error) {
            appendLog("Configuração inválida: " + error.getMessage());
        }
    }

    private void stopSync() {
        appendLog("Solicitando parada segura...");
        executor.execute(() -> PythonBridge.requestStop(getApplicationContext()));
        stopService(new Intent(this, SyncService.class));
    }

    private JSONObject accountJson() {
        JSONObject json = new JSONObject();
        try {
            json.put("api_id", Integer.parseInt(text(apiIdInput)));
            json.put("api_hash", text(apiHashInput));
            json.put("files_dir", getFilesDir().getAbsolutePath());
        } catch (JSONException ignored) {
        }
        return json;
    }

    private void runPython(String method, ResultHandler handler, Object... args) {
        setButtonsEnabled(false);
        executor.execute(() -> {
            try {
                String raw = PythonBridge.call(getApplicationContext(), method, args);
                JSONObject result = new JSONObject(raw);
                runOnUiThread(() -> handler.handle(result));
            } catch (Throwable error) {
                runOnUiThread(() -> appendLog("Erro: " + error.getMessage()));
            } finally {
                runOnUiThread(() -> setButtonsEnabled(true));
            }
        });
    }

    private boolean validateAccount() {
        if (text(apiIdInput).isEmpty() || text(apiHashInput).isEmpty()) {
            toast("Informe o API ID e o API Hash.");
            return false;
        }
        try {
            Integer.parseInt(text(apiIdInput));
            return true;
        } catch (NumberFormatException error) {
            toast("O API ID precisa ser numérico.");
            return false;
        }
    }

    private boolean validateRoute() {
        if (text(sourceInput).isEmpty() || text(targetInput).isEmpty()) {
            toast("Informe a origem e o destino da rota.");
            return false;
        }
        return true;
    }

    private void setButtonsEnabled(boolean enabled) {
        int[] ids = {
                R.id.sendCodeButton,
                R.id.checkSessionButton,
                R.id.confirmLoginButton,
                R.id.listDialogsButton,
                R.id.listTopicsButton
        };
        for (int id : ids) findViewById(id).setEnabled(enabled);
    }

    private void appendLog(String message) {
        if (message == null || message.trim().isEmpty()) return;
        String previous = logText.getText().toString();
        if ("Pronto para configurar.".equals(previous)) previous = "";
        logText.setText(previous.isEmpty() ? message : previous + "\n" + message);
    }

    private void saveFields() {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("api_id", text(apiIdInput))
                .putString("api_hash", text(apiHashInput))
                .putString("phone", text(phoneInput))
                .putString("route_name", text(routeNameInput))
                .putString("source", text(sourceInput))
                .putString("source_topic", text(sourceTopicInput))
                .putString("target", text(targetInput))
                .putString("target_topic", text(targetTopicInput))
                .putString("retro_limit", text(retroLimitInput))
                .putString("retro_start", text(retroStartIdInput))
                .apply();
    }

    private void restoreFields() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        apiIdInput.setText(prefs.getString("api_id", ""));
        apiHashInput.setText(prefs.getString("api_hash", ""));
        phoneInput.setText(prefs.getString("phone", ""));
        routeNameInput.setText(prefs.getString("route_name", "Rota Android"));
        sourceInput.setText(prefs.getString("source", ""));
        sourceTopicInput.setText(prefs.getString("source_topic", ""));
        targetInput.setText(prefs.getString("target", ""));
        targetTopicInput.setText(prefs.getString("target_topic", ""));
        retroLimitInput.setText(prefs.getString("retro_limit", "100"));
        retroStartIdInput.setText(prefs.getString("retro_start", "0"));
        phoneCodeHash = prefs.getString("phone_code_hash", "");
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    NOTIFICATION_PERMISSION_REQUEST
            );
        }
    }

    private void clearPhoneCodeHash() {
        phoneCodeHash = "";
        getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .remove("phone_code_hash")
                .apply();
    }

    private static void putOptionalInt(JSONObject json, String key, String value) throws JSONException {
        json.put(key, value.isEmpty() ? JSONObject.NULL : Integer.parseInt(value));
    }

    private static int positiveInt(String value, int fallback) {
        try {
            return Math.max(1, Integer.parseInt(value));
        } catch (NumberFormatException error) {
            return fallback;
        }
    }

    private static int nonNegativeInt(String value, int fallback) {
        try {
            return Math.max(0, Integer.parseInt(value));
        } catch (NumberFormatException error) {
            return fallback;
        }
    }

    private static String text(EditText field) {
        return field.getText().toString().trim();
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private interface ResultHandler {
        void handle(JSONObject result);
    }
}
