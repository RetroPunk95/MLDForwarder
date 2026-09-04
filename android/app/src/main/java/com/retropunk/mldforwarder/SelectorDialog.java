package com.retropunk.mldforwarder;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

final class SelectorDialog extends Dialog {
    interface SingleListener {
        void onSelected(Item item);
    }

    interface MultiListener {
        void onConfirmed(List<Item> items);
    }

    interface ItemActionListener {
        void onAction(Item item);
    }

    static final class Item {
        final int index;
        final String id;
        final String title;
        final String subtitle;
        final String badge;
        final String kind;
        final String icon;

        Item(int index, String id, String title, String subtitle, String badge, String kind, String icon) {
            this.index = index;
            this.id = safe(id);
            this.title = safe(title);
            this.subtitle = safe(subtitle);
            this.badge = safe(badge);
            this.kind = safe(kind);
            this.icon = safe(icon);
        }
    }

    private final Activity activity;
    private final String title;
    private final String subtitle;
    private final ArrayList<Item> items;
    private final boolean multiple;
    private final boolean searchable;
    private final boolean filterable;
    private final String actionLabel;
    private final SingleListener singleListener;
    private final MultiListener multiListener;
    private final ItemActionListener itemActionListener;
    private final Set<Integer> selected = new LinkedHashSet<>();
    private final ArrayList<Item> visibleItems = new ArrayList<>();

    private PickerAdapter adapter;
    private EditText searchInput;
    private TextView emptyText;
    private TextView selectionCount;
    private Button primaryButton;
    private LinearLayout filters;
    private TextView filterAll;
    private TextView filterChannels;
    private TextView filterGroups;
    private TextView filterConversations;
    private String activeFilter = "Todos";

    private SelectorDialog(
            Activity activity,
            String title,
            String subtitle,
            List<Item> items,
            boolean multiple,
            boolean searchable,
            boolean filterable,
            String actionLabel,
            SingleListener singleListener,
            MultiListener multiListener,
            ItemActionListener itemActionListener
    ) {
        super(activity);
        this.activity = activity;
        this.title = title;
        this.subtitle = subtitle;
        this.items = new ArrayList<>(items);
        this.multiple = multiple;
        this.searchable = searchable;
        this.filterable = filterable;
        this.actionLabel = actionLabel;
        this.singleListener = singleListener;
        this.multiListener = multiListener;
        this.itemActionListener = itemActionListener;
        if (multiple) {
            for (Item item : items) selected.add(item.index);
        }
    }

    static void showSingle(
            Activity activity,
            String title,
            String subtitle,
            List<Item> items,
            boolean searchable,
            boolean filterable,
            SingleListener listener
    ) {
        new SelectorDialog(activity, title, subtitle, items, false, searchable, filterable,
                "", listener, null, null).show();
    }

    static void showSingleWithActions(
            Activity activity,
            String title,
            String subtitle,
            List<Item> items,
            boolean searchable,
            SingleListener listener,
            ItemActionListener actionListener
    ) {
        new SelectorDialog(activity, title, subtitle, items, false, searchable, false,
                "", listener, null, actionListener).show();
    }

    static void showMulti(
            Activity activity,
            String title,
            String subtitle,
            String actionLabel,
            List<Item> items,
            MultiListener listener
    ) {
        new SelectorDialog(activity, title, subtitle, items, true, false, false,
                actionLabel, null, listener, null).show();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        setContentView(R.layout.dialog_selector);
        bindViews();
        configureHeader();
        configureSearch();
        configureFilters();
        configureSelectionControls();
        configureList();
        configureFooter();
        applyFilter();
    }

    @Override
    public void show() {
        super.show();
        Window window = getWindow();
        if (window == null) return;
        window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        window.setDimAmount(0.78f);
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        window.setGravity(Gravity.BOTTOM);
        int screenHeight = activity.getResources().getDisplayMetrics().heightPixels;
        int maxHeight = Math.min(dp(690), Math.round(screenHeight * 0.88f));
        window.setLayout(WindowManager.LayoutParams.MATCH_PARENT, maxHeight);
        window.getDecorView().setPadding(0, 0, 0, 0);
    }

    private void bindViews() {
        searchInput = findViewById(R.id.selectorSearchInput);
        emptyText = findViewById(R.id.selectorEmptyText);
        selectionCount = findViewById(R.id.selectorSelectionCount);
        primaryButton = findViewById(R.id.selectorPrimaryButton);
        filters = findViewById(R.id.selectorFilters);
        filterAll = findViewById(R.id.selectorFilterAll);
        filterChannels = findViewById(R.id.selectorFilterChannels);
        filterGroups = findViewById(R.id.selectorFilterGroups);
        filterConversations = findViewById(R.id.selectorFilterConversations);
    }

    private void configureHeader() {
        ((TextView) findViewById(R.id.selectorTitle)).setText(title);
        TextView subtitleView = findViewById(R.id.selectorSubtitle);
        subtitleView.setText(subtitle);
        subtitleView.setVisibility(subtitle.isEmpty() ? View.GONE : View.VISIBLE);
        findViewById(R.id.selectorCloseButton).setOnClickListener(v -> dismiss());
    }

    private void configureSearch() {
        searchInput.setVisibility(searchable ? View.VISIBLE : View.GONE);
        if (!searchable) return;
        searchInput.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { applyFilter(); }
            @Override public void afterTextChanged(Editable s) { }
        });
    }

    private void configureFilters() {
        filters.setVisibility(filterable ? View.VISIBLE : View.GONE);
        if (!filterable) return;
        filterAll.setOnClickListener(v -> selectFilter("Todos"));
        filterChannels.setOnClickListener(v -> selectFilter("Canal"));
        filterGroups.setOnClickListener(v -> selectFilter("Grupo"));
        filterConversations.setOnClickListener(v -> selectFilter("Conversa"));
        updateFilterStyles();
    }

    private void configureSelectionControls() {
        View controls = findViewById(R.id.selectorSelectionControls);
        controls.setVisibility(multiple ? View.VISIBLE : View.GONE);
        if (!multiple) return;
        findViewById(R.id.selectorSelectAllButton).setOnClickListener(v -> {
            selected.clear();
            for (Item item : items) selected.add(item.index);
            adapter.notifyDataSetChanged();
            updateSelectionState();
        });
        findViewById(R.id.selectorClearButton).setOnClickListener(v -> {
            selected.clear();
            adapter.notifyDataSetChanged();
            updateSelectionState();
        });
    }

    private void configureList() {
        ListView list = findViewById(R.id.selectorList);
        adapter = new PickerAdapter();
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> {
            Item item = visibleItems.get(position);
            if (multiple) {
                if (selected.contains(item.index)) selected.remove(item.index);
                else selected.add(item.index);
                adapter.notifyDataSetChanged();
                updateSelectionState();
                return;
            }
            dismiss();
            if (singleListener != null) singleListener.onSelected(item);
        });
    }

    private void configureFooter() {
        Button cancel = findViewById(R.id.selectorCancelButton);
        cancel.setOnClickListener(v -> dismiss());
        primaryButton.setVisibility(multiple ? View.VISIBLE : View.GONE);
        cancel.setText(multiple ? "Cancelar" : "Fechar");
        if (!multiple) return;
        primaryButton.setOnClickListener(v -> {
            if (selected.isEmpty()) return;
            ArrayList<Item> chosen = new ArrayList<>();
            for (Item item : items) {
                if (selected.contains(item.index)) chosen.add(item);
            }
            dismiss();
            if (multiListener != null) multiListener.onConfirmed(chosen);
        });
        updateSelectionState();
    }

    private void selectFilter(String filter) {
        activeFilter = filter;
        updateFilterStyles();
        applyFilter();
    }

    private void updateFilterStyles() {
        setChipState(filterAll, "Todos".equals(activeFilter));
        setChipState(filterChannels, "Canal".equals(activeFilter));
        setChipState(filterGroups, "Grupo".equals(activeFilter));
        setChipState(filterConversations, "Conversa".equals(activeFilter));
    }

    private void setChipState(TextView chip, boolean active) {
        chip.setBackgroundResource(active ? R.drawable.bg_filter_active : R.drawable.bg_filter_inactive);
        chip.setTextColor(activity.getColor(active ? R.color.text_primary : R.color.text_secondary));
    }

    private void applyFilter() {
        String query = normalize(searchable ? searchInput.getText().toString() : "");
        visibleItems.clear();
        for (Item item : items) {
            boolean kindMatches = "Todos".equals(activeFilter) || activeFilter.equals(item.kind);
            String haystack = normalize(item.title + " " + item.subtitle + " " + item.id);
            if (kindMatches && (query.isEmpty() || haystack.contains(query))) visibleItems.add(item);
        }
        if (adapter != null) adapter.notifyDataSetChanged();
        emptyText.setVisibility(visibleItems.isEmpty() ? View.VISIBLE : View.GONE);
    }

    private void updateSelectionState() {
        int count = selected.size();
        selectionCount.setText(count == 1 ? "1 rota selecionada" : count + " rotas selecionadas");
        primaryButton.setEnabled(count > 0);
        primaryButton.setAlpha(count > 0 ? 1f : 0.45f);
        primaryButton.setText(count > 0 ? actionLabel + " · " + count : actionLabel);
    }

    private final class PickerAdapter extends BaseAdapter {
        @Override public int getCount() { return visibleItems.size(); }
        @Override public Item getItem(int position) { return visibleItems.get(position); }
        @Override public long getItemId(int position) { return getItem(position).index; }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            View row = convertView;
            if (row == null) {
                row = LayoutInflater.from(activity).inflate(R.layout.item_selector, parent, false);
            }
            Item item = getItem(position);
            boolean checked = multiple && selected.contains(item.index);
            row.setBackgroundResource(checked ? R.drawable.bg_selector_item_selected : R.drawable.bg_selector_item);

            TextView icon = row.findViewById(R.id.selectorItemIcon);
            TextView title = row.findViewById(R.id.selectorItemTitle);
            TextView subtitle = row.findViewById(R.id.selectorItemSubtitle);
            TextView badge = row.findViewById(R.id.selectorItemBadge);
            ImageView check = row.findViewById(R.id.selectorItemCheck);
            ImageView action = row.findViewById(R.id.selectorItemAction);

            icon.setText(item.icon.isEmpty() ? "•" : item.icon);
            title.setText(item.title);
            subtitle.setText(item.subtitle);
            subtitle.setVisibility(item.subtitle.isEmpty() ? View.GONE : View.VISIBLE);
            badge.setText(item.badge);
            badge.setVisibility(item.badge.isEmpty() ? View.GONE : View.VISIBLE);
            check.setVisibility(multiple ? View.VISIBLE : View.GONE);
            if (multiple) {
                check.setImageResource(checked ? R.drawable.ic_check_selected : R.drawable.ic_check_unselected);
            }
            boolean hasAction = !multiple && itemActionListener != null;
            action.setVisibility(hasAction ? View.VISIBLE : View.GONE);
            if (hasAction) {
                action.setContentDescription("Excluir " + item.title);
                action.setOnClickListener(v -> {
                    dismiss();
                    itemActionListener.onAction(item);
                });
            } else {
                action.setOnClickListener(null);
            }
            return row;
        }
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String normalize(String value) {
        String normalized = Normalizer.normalize(safe(value), Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "");
        return normalized.toLowerCase(Locale.ROOT).trim();
    }
}
