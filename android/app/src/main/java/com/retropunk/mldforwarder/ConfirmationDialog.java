package com.retropunk.mldforwarder;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;

final class ConfirmationDialog extends Dialog {
    private final String title;
    private final String message;
    private final String actionLabel;
    private final Runnable onConfirm;

    private ConfirmationDialog(Activity activity, String title, String message,
                               String actionLabel, Runnable onConfirm) {
        super(activity);
        this.title = title;
        this.message = message;
        this.actionLabel = actionLabel;
        this.onConfirm = onConfirm;
    }

    static void show(Activity activity, String title, String message,
                     String actionLabel, Runnable onConfirm) {
        new ConfirmationDialog(activity, title, message, actionLabel, onConfirm).show();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        setContentView(R.layout.dialog_confirmation);
        ((TextView) findViewById(R.id.confirmationTitle)).setText(title);
        ((TextView) findViewById(R.id.confirmationMessage)).setText(message);
        findViewById(R.id.confirmationCloseButton).setOnClickListener(v -> dismiss());
        findViewById(R.id.confirmationCancelButton).setOnClickListener(v -> dismiss());
        Button action = findViewById(R.id.confirmationActionButton);
        action.setText(actionLabel);
        action.setOnClickListener(v -> {
            dismiss();
            onConfirm.run();
        });
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
        window.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.WRAP_CONTENT);
        window.getDecorView().setPadding(0, 0, 0, 0);
    }
}
