package com.retropunk.mldforwarder;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String PREFS = "mld_alpha";
    private static final String ROUTES_KEY = "routes_v1";
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
    private TextView routeSummaryText;
    private TextView logText;
    private SecurePrefs securePrefs;
    private JSONArray routes = new JSONArray();
    private int selectedRouteIndex = -1;
    private String phoneCodeHash = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        securePrefs = new SecurePrefs(this);
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
        saveFields();
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
        routeSummaryText = findViewById(R.id.routeSummaryText);
        logText = findViewById(R.id.logText);
        passwordInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    }

    private void bindActions() {
        findViewById(R.id.sendCodeButton).setOnClickListener(v -> sendCode());
        findViewById(R.id.checkSessionButton).setOnClickListener(v -> checkSession());
        findViewById(R.id.confirmLoginButton).setOnClickListener(v -> confirmLogin());
        findViewById(R.id.selectSourceButton).setOnClickListener(v -> listDialogs(true));
        findViewById(R.id.selectTargetButton).setOnClickListener(v -> listDialogs(false));
        findViewById(R.id.selectSourceTopicButton).setOnClickListener(v -> listTopics(true));
        findViewById(R.id.selectTargetTopicButton).setOnClickListener(v -> listTopics(false));
        findViewById(R.id.newRouteButton).setOnClickListener(v -> newRoute());
        findViewById(R.id.saveRouteButton).setOnClickListener(v -> saveRoute(true));
        findViewById(R.id.selectRouteButton).setOnClickListener(v -> selectRoute());
        findViewById(R.id.deleteRouteButton).setOnClickListener(v -> deleteRoute());
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
            securePrefs.putString("phone_code_hash", phoneCodeHash);
            appendLog(result.optString("message", result.optString("error", "Resposta recebida.")));
        }, accountJson().toString(), text(phoneInput));
    }

    private void checkSession() {
        if (!validateAccount()) return;
        saveFields();
        appendLog("Verificando sessão...");
        runPython("check_session", result ->
                        appendLog(result.optString("message", result.optString("error", "Verificação concluída."))),
                accountJson().toString());
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
                runPython("confirm_password", passwordResult -> {
                    if (passwordResult.optBoolean("authorized", false)) clearPhoneCodeHash();
                    appendLog(passwordResult.optString("message", passwordResult.optString("error", "Senha processada.")));
                }, accountJson().toString(), password);
            } else {
                if (result.optBoolean("authorized", false)) clearPhoneCodeHash();
                appendLog(result.optString("message", result.optString("error", "Código processado.")));
            }
        }, accountJson().toString(), text(phoneInput), text(codeInput), phoneCodeHash);
    }

    private void listDialogs(boolean selectingSource) {
        if (!validateAccount()) return;
        appendLog("Carregando canais e grupos...");
        runPython("list_dialogs", result -> {
            if (!result.optBoolean("ok", false)) {
                appendLog(result.optString("error", "Não foi possível listar os chats."));
                return;
            }
            JSONArray items = result.optJSONArray("items");
            if (items == null || items.length() == 0) {
                appendLog("Nenhum canal ou grupo encontrado.");
                return;
            }
            showDialogPicker(items, selectingSource);
        }, accountJson().toString());
    }

    private void showDialogPicker(JSONArray items, boolean selectingSource) {
        String[] labels = new String[items.length()];
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            labels[i] = item == null ? "Chat" : item.optString("label", item.optString("name", "Chat"));
        }
        new AlertDialog.Builder(this)
                .setTitle(selectingSource ? "Selecionar origem" : "Selecionar destino")
                .setItems(labels, (dialog, which) -> {
                    JSONObject item = items.optJSONObject(which);
                    if (item == null) return;
                    String id = item.optString("id", "");
                    if (selectingSource) {
                        sourceInput.setText(id);
                        sourceTopicInput.setText("");
                    } else {
                        targetInput.setText(id);
                        targetTopicInput.setText("");
                    }
                    appendLog((selectingSource ? "Origem: " : "Destino: ") + labels[which]);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void listTopics(boolean selectingSource) {
        if (!validateAccount()) return;
        EditText peerInput = selectingSource ? sourceInput : targetInput;
        if (text(peerInput).isEmpty()) {
            toast(selectingSource ? "Selecione primeiro a origem." : "Selecione primeiro o destino.");
            return;
        }
        appendLog("Carregando tópicos...");
        runPython("list_topics", result -> {
            if (!result.optBoolean("ok", false)) {
                appendLog(result.optString("error", "Não foi possível listar os tópicos."));
                return;
            }
            JSONArray items = result.optJSONArray("items");
            showTopicPicker(items == null ? new JSONArray() : items, selectingSource);
        }, accountJson().toString(), text(peerInput));
    }

    private void showTopicPicker(JSONArray items, boolean selectingSource) {
        String[] labels = new String[items.length() + 1];
        labels[0] = "Sem tópico (chat inteiro)";
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            labels[i + 1] = item == null ? "Tópico" : item.optString("label", item.optString("title", "Tópico"));
        }
        new AlertDialog.Builder(this)
                .setTitle(selectingSource ? "Tópico de origem" : "Tópico de destino")
                .setItems(labels, (dialog, which) -> {
                    EditText field = selectingSource ? sourceTopicInput : targetTopicInput;
                    if (which == 0) {
                        field.setText("");
                        return;
                    }
                    JSONObject item = items.optJSONObject(which - 1);
                    if (item != null) field.setText(item.optString("id", ""));
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void newRoute() {
        selectedRouteIndex = -1;
        routeNameInput.setText("Rota " + (routes.length() + 1));
        sourceInput.setText("");
        sourceTopicInput.setText("");
        targetInput.setText("");
        targetTopicInput.setText("");
        retroLimitInput.setText("100");
        retroStartIdInput.setText("0");
        updateRouteSummary();
    }

    private boolean saveRoute(boolean notify) {
        if (!validateRoute()) return false;
        try {
            JSONObject route = routeJson();
            if (selectedRouteIndex >= 0 && selectedRouteIndex < routes.length()) {
                routes.put(selectedRouteIndex, route);
            } else {
                routes.put(route);
                selectedRouteIndex = routes.length() - 1;
            }
            persistRoutes();
            updateRouteSummary();
            if (notify) toast("Rota salva.");
            return true;
        } catch (JSONException | NumberFormatException error) {
            appendLog("Não foi possível salvar a rota: " + error.getMessage());
            return false;
        }
    }

    private void selectRoute() {
        if (routes.length() == 0) {
            toast("Nenhuma rota salva.");
            return;
        }
        String[] labels = new String[routes.length()];
        for (int i = 0; i < routes.length(); i++) {
            JSONObject route = routes.optJSONObject(i);
            labels[i] = route == null ? "Rota " + (i + 1) : route.optString("name", "Rota " + (i + 1));
        }
        new AlertDialog.Builder(this)
                .setTitle("Rotas salvas")
                .setItems(labels, (dialog, which) -> loadRoute(which))
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void loadRoute(int index) {
        JSONObject route = routes.optJSONObject(index);
        if (route == null) return;
        selectedRouteIndex = index;
        routeNameInput.setText(route.optString("name", "Rota " + (index + 1)));
        sourceInput.setText(route.optString("source", ""));
        sourceTopicInput.setText(optionalNumber(route, "source_topic"));
        targetInput.setText(route.optString("target", ""));
        targetTopicInput.setText(optionalNumber(route, "target_topic"));
        retroLimitInput.setText(String.valueOf(route.optInt("retro_limit", 100)));
        retroStartIdInput.setText(String.valueOf(route.optInt("retro_start_id", 0)));
        updateRouteSummary();
    }

    private void deleteRoute() {
        if (selectedRouteIndex < 0 || selectedRouteIndex >= routes.length()) {
            toast("Selecione uma rota salva para excluir.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Excluir rota?")
                .setMessage("O progresso registrado não será apagado.")
                .setPositiveButton("Excluir", (dialog, which) -> {
                    routes.remove(selectedRouteIndex);
                    selectedRouteIndex = -1;
                    persistRoutes();
                    newRoute();
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void startSync(String mode) {
        if (!validateAccount()) return;
        if (hasCompleteRoute()) {
            if (!saveRoute(false)) return;
        } else if (routes.length() == 0) {
            toast("Salve pelo menos uma rota antes de iniciar.");
            return;
        }
        saveFields();
        try {
            JSONObject config = accountJson();
            config.put("files_dir", getFilesDir().getAbsolutePath());
            config.put("routes", routes);
            config.put("interval", 5);
            config.put("batch_size", 100);

            Intent service = new Intent(this, SyncService.class);
            service.putExtra(SyncService.EXTRA_MODE, mode);
            service.putExtra(SyncService.EXTRA_CONFIG, config.toString());
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(service);
            } else {
                startService(service);
            }
            appendLog("Iniciando " + routes.length() + " rota(s) em modo " + mode + ".");
        } catch (JSONException error) {
            appendLog("Configuração inválida: " + error.getMessage());
        }
    }

    private void stopSync() {
        appendLog("Solicitando parada segura...");
        executor.execute(() -> PythonBridge.requestStop(getApplicationContext()));
        stopService(new Intent(this, SyncService.class));
    }

    private JSONObject routeJson() throws JSONException {
        JSONObject route = new JSONObject();
        route.put("name", text(routeNameInput).isEmpty() ? "Rota " + (routes.length() + 1) : text(routeNameInput));
        route.put("source", text(sourceInput));
        putOptionalInt(route, "source_topic", text(sourceTopicInput));
        route.put("target", text(targetInput));
        putOptionalInt(route, "target_topic", text(targetTopicInput));
        route.put("retro_limit", positiveInt(text(retroLimitInput), 100));
        route.put("retro_start_id", nonNegativeInt(text(retroStartIdInput), 0));
        return route;
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
        if (!hasCompleteRoute()) {
            toast("Informe a origem e o destino da rota.");
            return false;
        }
        return true;
    }

    private boolean hasCompleteRoute() {
        return !text(sourceInput).isEmpty() && !text(targetInput).isEmpty();
    }

    private void setButtonsEnabled(boolean enabled) {
        int[] ids = {
                R.id.sendCodeButton, R.id.checkSessionButton, R.id.confirmLoginButton,
                R.id.selectSourceButton, R.id.selectTargetButton,
                R.id.selectSourceTopicButton, R.id.selectTargetTopicButton
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
        try {
            securePrefs.putString("api_id", text(apiIdInput));
            securePrefs.putString("api_hash", text(apiHashInput));
            securePrefs.putString("phone", text(phoneInput));
        } catch (IllegalStateException error) {
            appendLog(error.getMessage());
        }
    }

    private void restoreFields() {
        SharedPreferences legacy = getSharedPreferences(PREFS, MODE_PRIVATE);
        migrateSensitiveField(legacy, "api_id");
        migrateSensitiveField(legacy, "api_hash");
        migrateSensitiveField(legacy, "phone");
        migrateSensitiveField(legacy, "phone_code_hash");

        apiIdInput.setText(securePrefs.getString("api_id", ""));
        apiHashInput.setText(securePrefs.getString("api_hash", ""));
        phoneInput.setText(securePrefs.getString("phone", ""));
        phoneCodeHash = securePrefs.getString("phone_code_hash", "");

        String rawRoutes = legacy.getString(ROUTES_KEY, "[]");
        try {
            routes = new JSONArray(rawRoutes);
        } catch (JSONException error) {
            routes = new JSONArray();
        }
        if (routes.length() > 0) {
            loadRoute(0);
        } else {
            routeNameInput.setText(legacy.getString("route_name", "Rota Android"));
            sourceInput.setText(legacy.getString("source", ""));
            sourceTopicInput.setText(legacy.getString("source_topic", ""));
            targetInput.setText(legacy.getString("target", ""));
            targetTopicInput.setText(legacy.getString("target_topic", ""));
            retroLimitInput.setText(legacy.getString("retro_limit", "100"));
            retroStartIdInput.setText(legacy.getString("retro_start", "0"));
            updateRouteSummary();
        }
    }

    private void migrateSensitiveField(SharedPreferences legacy, String key) {
        if (!legacy.contains(key)) return;
        String value = legacy.getString(key, "");
        if (!value.isEmpty() && securePrefs.getString(key, "").isEmpty()) {
            securePrefs.putString(key, value);
        }
        legacy.edit().remove(key).apply();
    }

    private void persistRoutes() {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(ROUTES_KEY, routes.toString())
                .apply();
    }

    private void updateRouteSummary() {
        String selected = selectedRouteIndex >= 0 ? " · editando " + (selectedRouteIndex + 1) : " · nova rota";
        routeSummaryText.setText(routes.length() + " rota(s) salva(s)" + selected);
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_PERMISSION_REQUEST);
        }
    }

    private void clearPhoneCodeHash() {
        phoneCodeHash = "";
        securePrefs.remove("phone_code_hash");
    }

    private static String optionalNumber(JSONObject value, String key) {
        if (value.isNull(key)) return "";
        int number = value.optInt(key, 0);
        return number <= 0 ? "" : String.valueOf(number);
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
