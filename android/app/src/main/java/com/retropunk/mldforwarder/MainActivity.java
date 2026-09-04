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
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final String PREFS = "mld_alpha";
    private static final String ROUTES_KEY = "routes_v1";
    private static final int NOTIFICATION_PERMISSION_REQUEST = 83;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String message = intent.getStringExtra(SyncService.EXTRA_LOG);
            appendLog(message);
            if ("Sincronização encerrada.".equals(message)) {
                updateServiceStatus(false, "");
            }
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
    private TextView serviceStatusText;
    private TextView homeSyncDescriptionText;
    private TextView homeRouteCountText;
    private TextView homeAccountMetricText;
    private TextView homeCurrentRouteTitleText;
    private TextView homeCurrentRouteFlowText;
    private TextView headerRouteCountText;
    private TextView accountStatusText;
    private View serviceStatusDot;
    private View homePanel;
    private View routesPanel;
    private View activityPanel;
    private View accountPanel;
    private String currentPanel = "home";
    private SecurePrefs securePrefs;
    private JSONArray routes = new JSONArray();
    private int selectedRouteIndex = -1;
    private String phoneCodeHash = "";
    private String sourceSelectionId = "";
    private String sourceSelectionLabel = "";
    private String sourceSelectionKind = "";
    private String sourceTopicSelectionId = "";
    private String sourceTopicSelectionLabel = "";
    private String targetSelectionId = "";
    private String targetSelectionLabel = "";
    private String targetSelectionKind = "";
    private String targetTopicSelectionId = "";
    private String targetTopicSelectionLabel = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        securePrefs = new SecurePrefs(this);
        bindViews();
        restoreFields();
        bindActions();
        showPanel("home");
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
        serviceStatusText = findViewById(R.id.serviceStatusText);
        homeSyncDescriptionText = findViewById(R.id.homeSyncDescriptionText);
        homeRouteCountText = findViewById(R.id.homeRouteCountText);
        homeAccountMetricText = findViewById(R.id.homeAccountMetricText);
        homeCurrentRouteTitleText = findViewById(R.id.homeCurrentRouteTitleText);
        homeCurrentRouteFlowText = findViewById(R.id.homeCurrentRouteFlowText);
        headerRouteCountText = findViewById(R.id.headerRouteCountText);
        accountStatusText = findViewById(R.id.accountStatusText);
        serviceStatusDot = findViewById(R.id.serviceStatusDot);
        homePanel = findViewById(R.id.homePanel);
        routesPanel = findViewById(R.id.routesPanel);
        activityPanel = findViewById(R.id.activityPanel);
        accountPanel = findViewById(R.id.accountPanel);
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
        findViewById(R.id.homeOpenRoutesButton).setOnClickListener(v -> showPanel("routes"));
        findViewById(R.id.homeRoutesMetricCard).setOnClickListener(v -> selectRoute());
        findViewById(R.id.homeAccountMetricCard).setOnClickListener(v -> checkSessionFromHome());
        findViewById(R.id.clearLogButton).setOnClickListener(v -> logText.setText("Pronto para configurar."));
        findViewById(R.id.navHome).setOnClickListener(v -> showPanel("home"));
        findViewById(R.id.navRoutes).setOnClickListener(v -> showPanel("routes"));
        findViewById(R.id.navActivity).setOnClickListener(v -> showPanel("activity"));
        findViewById(R.id.navAccount).setOnClickListener(v -> showPanel("account"));
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
        verifySession(false);
    }

    private void checkSessionFromHome() {
        if (!validateAccount()) {
            showPanel("account");
            return;
        }
        verifySession(true);
    }

    private void verifySession(boolean fromHome) {
        saveFields();
        homeAccountMetricText.setText("Verificando…");
        homeAccountMetricText.setTextColor(getColor(R.color.primary_light));
        appendLog("Verificando sessão...");
        runPython("check_session", result -> {
            boolean authorized = result.optBoolean("authorized", false);
            updateAccountStatus(authorized);
            appendLog(result.optString("message", result.optString("error", "Verificação concluída.")));
            if (fromHome) {
                if (authorized) {
                    toast("Sessão conectada.");
                } else {
                    showPanel("account");
                    toast("Conecte sua conta para continuar.");
                }
            }
        }, accountJson().toString());
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
                    boolean authorized = passwordResult.optBoolean("authorized", false);
                    if (authorized) clearPhoneCodeHash();
                    updateAccountStatus(authorized);
                    appendLog(passwordResult.optString("message", passwordResult.optString("error", "Senha processada.")));
                }, accountJson().toString(), password);
            } else {
                boolean authorized = result.optBoolean("authorized", false);
                if (authorized) clearPhoneCodeHash();
                updateAccountStatus(authorized);
                appendLog(result.optString("message", result.optString("error", "Código processado.")));
            }
        }, accountJson().toString(), text(phoneInput), text(codeInput), phoneCodeHash);
    }

    private void listDialogs(boolean selectingSource) {
        if (!validateAccount()) return;
        appendLog("Carregando canais, grupos e conversas...");
        runPython("list_dialogs", result -> {
            if (!result.optBoolean("ok", false)) {
                appendLog(result.optString("error", "Não foi possível listar os chats."));
                return;
            }
            JSONArray items = result.optJSONArray("items");
            if (items == null || items.length() == 0) {
                appendLog("Nenhum canal, grupo ou conversa encontrado.");
                return;
            }
            showDialogPicker(items, selectingSource);
        }, accountJson().toString());
    }

    private void showDialogPicker(JSONArray items, boolean selectingSource) {
        List<SelectorDialog.Item> pickerItems = new ArrayList<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item == null) continue;
            String name = item.optString("name", "Chat");
            String kind = item.optString("kind", "Conversa");
            String id = item.optString("id", "");
            String fullLabel = item.optString("label", "");
            String details = fullLabel.startsWith(name + " · ")
                    ? fullLabel.substring((name + " · ").length())
                    : kind;
            if (!id.isEmpty()) details += " · ID " + id;
            String badge = item.optBoolean("forum", false) ? "Fórum" : "";
            String icon = item.optBoolean("saved_messages", false)
                    ? "★"
                    : ("Canal".equals(kind) ? "#" : ("Grupo".equals(kind) ? "G" : "@"));
            pickerItems.add(new SelectorDialog.Item(i, id, name, details, badge, kind, icon));
        }
        SelectorDialog.showSingle(
                this,
                selectingSource ? "Selecionar origem" : "Selecionar destino",
                "Busque e escolha um canal, grupo, conversa ou Mensagens salvas.",
                pickerItems,
                true,
                true,
                selected -> {
                    JSONObject item = items.optJSONObject(selected.index);
                    if (item == null) return;
                    applyPeerSelection(selectingSource, item);
                    appendLog((selectingSource ? "Origem: " : "Destino: ") + selected.title);
                }
        );
    }

    private void applyPeerSelection(boolean selectingSource, JSONObject item) {
        String id = item.optString("id", "");
        String name = item.optString("name", id);
        String kind = item.optString("kind", "Chat");
        if (selectingSource) {
            sourceInput.setText(id);
            sourceTopicInput.setText("");
            sourceSelectionId = id;
            sourceSelectionLabel = name;
            sourceSelectionKind = kind;
            sourceTopicSelectionId = "";
            sourceTopicSelectionLabel = "";
        } else {
            targetInput.setText(id);
            targetTopicInput.setText("");
            targetSelectionId = id;
            targetSelectionLabel = name;
            targetSelectionKind = kind;
            targetTopicSelectionId = "";
            targetTopicSelectionLabel = "";
        }
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
        List<SelectorDialog.Item> pickerItems = new ArrayList<>();
        pickerItems.add(new SelectorDialog.Item(-1, "", "Chat inteiro",
                "Sincronizar sem restringir a um tópico", "", "Tópico", "∞"));
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item == null) continue;
            String title = item.optString("title", "Tópico");
            String id = item.optString("id", "");
            pickerItems.add(new SelectorDialog.Item(i, id, title, "ID " + id,
                    "Tópico", "Tópico", "T"));
        }
        SelectorDialog.showSingle(
                this,
                selectingSource ? "Tópico de origem" : "Tópico de destino",
                "Escolha um tópico ou use o chat inteiro.",
                pickerItems,
                items.length() > 8,
                false,
                selected -> applyTopicSelection(selectingSource, selected)
        );
    }

    private void applyTopicSelection(boolean selectingSource, SelectorDialog.Item item) {
        if (selectingSource) {
            sourceTopicInput.setText(item.id);
            sourceTopicSelectionId = item.id;
            sourceTopicSelectionLabel = item.index < 0 ? "" : item.title;
        } else {
            targetTopicInput.setText(item.id);
            targetTopicSelectionId = item.id;
            targetTopicSelectionLabel = item.index < 0 ? "" : item.title;
        }
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
        clearSelectionMetadata();
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
        List<SelectorDialog.Item> pickerItems = new ArrayList<>();
        for (int i = 0; i < routes.length(); i++) {
            JSONObject route = routes.optJSONObject(i);
            if (route == null) continue;
            pickerItems.add(routePickerItem(route, i));
        }
        SelectorDialog.showSingleWithActions(this, "Rotas salvas",
                "Escolha uma rota para visualizar ou editar.", pickerItems,
                routes.length() > 8,
                selected -> loadRoute(selected.index),
                selected -> confirmDeleteRoute(selected.index));
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
        sourceSelectionId = route.optString("source", "");
        sourceSelectionLabel = route.optString("source_label", "");
        sourceSelectionKind = route.optString("source_kind", "");
        sourceTopicSelectionId = optionalNumber(route, "source_topic");
        sourceTopicSelectionLabel = route.optString("source_topic_label", "");
        targetSelectionId = route.optString("target", "");
        targetSelectionLabel = route.optString("target_label", "");
        targetSelectionKind = route.optString("target_kind", "");
        targetTopicSelectionId = optionalNumber(route, "target_topic");
        targetTopicSelectionLabel = route.optString("target_topic_label", "");
        updateRouteSummary();
    }

    private void deleteRoute() {
        if (selectedRouteIndex < 0 || selectedRouteIndex >= routes.length()) {
            toast("Selecione uma rota salva para excluir.");
            return;
        }
        confirmDeleteRoute(selectedRouteIndex);
    }

    private void confirmDeleteRoute(int index) {
        JSONObject route = routes.optJSONObject(index);
        if (route == null) return;
        String name = route.optString("name", "Rota " + (index + 1));
        ConfirmationDialog.show(
                this,
                "Excluir rota?",
                "A rota “" + name + "” será removida. O progresso registrado não será apagado.",
                "Excluir rota",
                () -> deleteRouteAt(index)
        );
    }

    private void deleteRouteAt(int index) {
        if (index < 0 || index >= routes.length()) return;
        String name = routes.optJSONObject(index) == null
                ? "Rota " + (index + 1)
                : routes.optJSONObject(index).optString("name", "Rota " + (index + 1));
        routes.remove(index);
        if (selectedRouteIndex > index) selectedRouteIndex--;
        else if (selectedRouteIndex == index) selectedRouteIndex = -1;
        persistRoutes();

        if (routes.length() == 0) {
            newRoute();
        } else {
            int nextIndex = selectedRouteIndex >= 0
                    ? selectedRouteIndex
                    : Math.min(index, routes.length() - 1);
            loadRoute(nextIndex);
            selectRoute();
        }
        toast(name + " excluída.");
    }

    private void startSync(String mode) {
        if (!validateAccount()) return;
        if (hasCompleteRoute()) {
            if (!saveRoute(false)) return;
        } else if (routes.length() == 0) {
            toast("Salve pelo menos uma rota antes de iniciar.");
            return;
        }
        showRouteSelection(mode);
    }

    private void showRouteSelection(String mode) {
        String title = "retro".equals(mode) ? "Sincronização retroativa" : "Sincronização normal";
        String action = "retro".equals(mode) ? "Iniciar retroativa" : "Iniciar normal";
        List<SelectorDialog.Item> pickerItems = new ArrayList<>();
        for (int i = 0; i < routes.length(); i++) {
            JSONObject route = routes.optJSONObject(i);
            if (route != null) pickerItems.add(routePickerItem(route, i));
        }
        SelectorDialog.showMulti(this, title,
                "Marque as rotas que participarão desta execução.", action,
                pickerItems, selected -> {
            JSONArray selectedRoutes = new JSONArray();
            for (SelectorDialog.Item item : selected) {
                JSONObject route = routes.optJSONObject(item.index);
                if (route != null) selectedRoutes.put(route);
            }
            startSelectedRoutes(mode, selectedRoutes);
        });
    }

    private void startSelectedRoutes(String mode, JSONArray selectedRoutes) {
        saveFields();
        try {
            JSONObject config = accountJson();
            config.put("files_dir", getFilesDir().getAbsolutePath());
            config.put("routes", selectedRoutes);
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
            updateServiceStatus(true, mode);
            appendLog("Iniciando " + selectedRoutes.length() + " rota(s) em modo " + mode + ".");
        } catch (JSONException error) {
            appendLog("Configuração inválida: " + error.getMessage());
        }
    }

    private SelectorDialog.Item routePickerItem(JSONObject route, int index) {
        String name = route.optString("name", "Rota " + (index + 1));
        String flow = routeEndpointLabel(route, "source", "Origem")
                + "  →  " + routeEndpointLabel(route, "target", "Destino");
        return new SelectorDialog.Item(index, String.valueOf(index), name, flow,
                "Normal + retroativa", "Rota", "↗");
    }

    private void stopSync() {
        appendLog("Solicitando parada segura...");
        executor.execute(() -> PythonBridge.requestStop(getApplicationContext()));
        // O motor confirma a etapa em andamento e encerra o próprio serviço.
        // Destruir o serviço aqui permitia reiniciar enquanto o Python ainda enviava.
        serviceStatusText.setText("Encerrando com segurança...");
        serviceStatusText.setTextColor(getColor(R.color.text_secondary));
    }

    private JSONObject routeJson() throws JSONException {
        JSONObject route = new JSONObject();
        route.put("name", text(routeNameInput).isEmpty() ? "Rota " + (routes.length() + 1) : text(routeNameInput));
        route.put("source", text(sourceInput));
        putOptionalInt(route, "source_topic", text(sourceTopicInput));
        route.put("target", text(targetInput));
        putOptionalInt(route, "target_topic", text(targetTopicInput));
        putSelectionMetadata(route, "source", text(sourceInput), sourceSelectionId,
                sourceSelectionLabel, sourceSelectionKind);
        putTopicMetadata(route, "source_topic", text(sourceTopicInput),
                sourceTopicSelectionId, sourceTopicSelectionLabel);
        putSelectionMetadata(route, "target", text(targetInput), targetSelectionId,
                targetSelectionLabel, targetSelectionKind);
        putTopicMetadata(route, "target_topic", text(targetTopicInput),
                targetTopicSelectionId, targetTopicSelectionLabel);
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
        findViewById(R.id.homeRoutesMetricCard).setEnabled(enabled);
        findViewById(R.id.homeAccountMetricCard).setEnabled(enabled);
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
        String count = String.valueOf(routes.length());
        headerRouteCountText.setText(count);
        homeRouteCountText.setText(routes.length() < 10 ? "0" + count : count);
        homeSyncDescriptionText.setText(routes.length() == 0
                ? "Cadastre uma rota para começar."
                : routes.length() + " rota(s) pronta(s) para sincronização normal ou retroativa.");

        JSONObject selectedRoute = selectedRouteIndex >= 0 ? routes.optJSONObject(selectedRouteIndex) : null;
        if (selectedRoute == null && routes.length() > 0) selectedRoute = routes.optJSONObject(0);
        if (selectedRoute == null) {
            homeCurrentRouteTitleText.setText("Nenhuma rota selecionada");
            homeCurrentRouteFlowText.setText("Abra o gerenciador para configurar origem e destino.");
        } else {
            homeCurrentRouteTitleText.setText(selectedRoute.optString("name", "Rota"));
            String source = routeEndpointLabel(selectedRoute, "source", "Origem");
            String target = routeEndpointLabel(selectedRoute, "target", "Destino");
            homeCurrentRouteFlowText.setText(source + "  →  " + target);
        }
    }

    private String routeEndpointLabel(JSONObject route, String prefix, String fallback) {
        String id = route.optString(prefix, fallback);
        String label = route.optString(prefix + "_label", "");
        String topic = route.optString(prefix + "_topic_label", "");
        String value = label.isEmpty() ? id : label;
        return topic.isEmpty() ? value : value + " · " + topic;
    }

    private void putSelectionMetadata(JSONObject route, String prefix, String currentId,
                                      String selectedId, String label, String kind) throws JSONException {
        if (currentId.equals(selectedId) && !label.isEmpty()) {
            route.put(prefix + "_label", label);
            route.put(prefix + "_kind", kind);
        }
    }

    private void putTopicMetadata(JSONObject route, String prefix, String currentId,
                                  String selectedId, String label) throws JSONException {
        if (!currentId.isEmpty() && currentId.equals(selectedId) && !label.isEmpty()) {
            route.put(prefix + "_label", label);
        }
    }

    private void clearSelectionMetadata() {
        sourceSelectionId = "";
        sourceSelectionLabel = "";
        sourceSelectionKind = "";
        sourceTopicSelectionId = "";
        sourceTopicSelectionLabel = "";
        targetSelectionId = "";
        targetSelectionLabel = "";
        targetSelectionKind = "";
        targetTopicSelectionId = "";
        targetTopicSelectionLabel = "";
    }

    private void showPanel(String panel) {
        currentPanel = panel;
        homePanel.setVisibility("home".equals(panel) ? View.VISIBLE : View.GONE);
        routesPanel.setVisibility("routes".equals(panel) ? View.VISIBLE : View.GONE);
        activityPanel.setVisibility("activity".equals(panel) ? View.VISIBLE : View.GONE);
        accountPanel.setVisibility("account".equals(panel) ? View.VISIBLE : View.GONE);

        updateNavItem(R.id.navHome, R.id.navHomeIcon, R.id.navHomeLabel, "home".equals(panel));
        updateNavItem(R.id.navRoutes, R.id.navRoutesIcon, R.id.navRoutesLabel, "routes".equals(panel));
        updateNavItem(R.id.navActivity, R.id.navActivityIcon, R.id.navActivityLabel, "activity".equals(panel));
        updateNavItem(R.id.navAccount, R.id.navAccountIcon, R.id.navAccountLabel, "account".equals(panel));
    }

    private void updateNavItem(int containerId, int iconId, int labelId, boolean selected) {
        LinearLayout container = findViewById(containerId);
        ImageView icon = findViewById(iconId);
        TextView label = findViewById(labelId);
        int color = getColor(selected ? R.color.primary_light : R.color.text_muted);
        container.setBackgroundResource(selected ? R.drawable.bg_nav_selected : android.R.color.transparent);
        icon.setColorFilter(color);
        label.setTextColor(color);
    }

    private void updateAccountStatus(boolean authorized) {
        accountStatusText.setText(authorized ? "Conta conectada" : "Sessão não conectada");
        accountStatusText.setTextColor(getColor(authorized ? R.color.success : R.color.text_primary));
        homeAccountMetricText.setText(authorized ? "Conectada" : "Verificar");
        homeAccountMetricText.setTextColor(getColor(authorized ? R.color.success : R.color.text_primary));
    }

    private void updateServiceStatus(boolean running, String mode) {
        serviceStatusDot.setBackgroundResource(running ? R.drawable.bg_status_active : R.drawable.bg_status_idle);
        if (running) {
            serviceStatusText.setText("Sincronização " + ("retro".equals(mode) ? "retroativa" : "normal") + " ativa");
            serviceStatusText.setTextColor(getColor(R.color.success));
        } else {
            serviceStatusText.setText("Serviço pausado");
            serviceStatusText.setTextColor(getColor(R.color.text_secondary));
        }
    }

    @Override
    public void onBackPressed() {
        if (!"home".equals(currentPanel)) {
            showPanel("home");
        } else {
            super.onBackPressed();
        }
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
