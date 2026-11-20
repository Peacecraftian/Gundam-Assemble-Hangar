package app.hangar.prototype;

import android.app.AlertDialog;
import android.text.InputType;
import android.view.Gravity;
import android.widget.*;

final class ConsoleForm {
    final TabletActivity host;
    final LinearLayout body;
    final ScrollView scroll;

    ConsoleForm(TabletActivity host) {
        this.host = host;
        scroll = new ScrollView(host);
        body = new LinearLayout(host);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(host.dp(18),host.dp(8),host.dp(18),host.dp(8));
        body.setFocusableInTouchMode(true);
        scroll.addView(body);
    }

    TextView label(String value) {
        TextView text = new TextView(host);
        text.setText(value);
        text.setTextSize(16);
        body.addView(text);
        return text;
    }

    LinearLayout row() {
        LinearLayout row = new LinearLayout(host);
        row.setGravity(Gravity.CENTER_VERTICAL);
        body.addView(row);
        return row;
    }

    Button button(LinearLayout row, String title, Runnable click) {
        Button b = ConsoleSkin.button(host);
        b.setText(title);
        b.setMinHeight(host.dp(48));
        b.setOnClickListener(v -> click.run());
        row.addView(b,new LinearLayout.LayoutParams(0,-2,1));
        return b;
    }

    EditText number(String title, int value, int min, int max) {
        label(title);
        LinearLayout row = row();
        EditText field = new EditText(host);
        field.setSingleLine();
        field.setInputType(InputType.TYPE_CLASS_NUMBER | (min < 0 ? InputType.TYPE_NUMBER_FLAG_SIGNED : 0));
        field.setText(String.valueOf(value));
        field.setSelectAllOnFocus(true);
        field.setGravity(Gravity.CENTER);
        field.setContentDescription(title);
        button(row,"−",() -> step(field,-1,min,max));
        row.addView(field,new LinearLayout.LayoutParams(0,-2,2));
        button(row,"+",() -> step(field,1,min,max));
        return field;
    }

    private void step(EditText field, int delta, int min, int max) {
        int n;
        try { n = Integer.parseInt(field.getText().toString()); }
        catch (NumberFormatException e) { n = 0; }
        field.setText(String.valueOf(Math.max(min, Math.min((long) max, (long)n + delta))));
    }

    int value(EditText field, int min, int max) {
        try {
            int n = Integer.parseInt(field.getText().toString().trim());
            if (n >= min && n <= max) return n;
        } catch (NumberFormatException ignored) { }
        field.requestFocus();
        throw new IllegalArgumentException("Check " + field.getContentDescription() + ".");
    }

    EditText text(String title, String value) {
        label(title);
        EditText edit = new EditText(host);
        edit.setText(value);
        edit.setContentDescription(title);
        body.addView(edit);
        return edit;
    }

    Spinner choices(String title, String[] values, int current) {
        label(title);
        Spinner spinner = new Spinner(host,Spinner.MODE_DIALOG);
        spinner.setContentDescription(title);
        spinner.setMinimumHeight(host.dp(48));
        spinner.setAdapter(new ArrayAdapter<>(host,android.R.layout.simple_spinner_dropdown_item,values));
        spinner.setSelection(current);
        body.addView(spinner);
        return spinner;
    }

    interface Submit { boolean save(); }
    void show(String title, String submit, Submit onSubmit) {
        TextView error = label("");
        error.setTextColor(0xffffa090);
        error.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        AlertDialog dialog = ConsoleSkin.dialog(host).setTitle(title).setView(scroll)
                .setNegativeButton("Cancel",null).setPositiveButton(submit,null).create();
        dialog.show();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try { if (onSubmit.save()) dialog.dismiss(); }
            catch (IllegalArgumentException e) { error.setText(e.getMessage()); scroll.smoothScrollTo(0,body.getHeight()); }
        });
    }
}
