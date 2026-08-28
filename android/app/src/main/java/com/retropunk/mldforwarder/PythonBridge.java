package com.retropunk.mldforwarder;

import android.content.Context;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

final class PythonBridge {
    private PythonBridge() {
    }

    static synchronized PyObject module(Context context) {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(context.getApplicationContext()));
        }
        return Python.getInstance().getModule("mobile_engine");
    }

    static String call(Context context, String method, Object... args) {
        PyObject result = module(context).callAttr(method, args);
        return result == null ? "" : result.toString();
    }

    static void requestStop(Context context) {
        try {
            call(context, "request_stop", context.getFilesDir().getAbsolutePath());
        } catch (RuntimeException ignored) {
            // O serviço também é interrompido pelo Android; a flag é uma parada cooperativa.
        }
    }
}
