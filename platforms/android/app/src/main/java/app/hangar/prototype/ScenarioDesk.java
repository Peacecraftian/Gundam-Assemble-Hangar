package app.hangar.prototype;

import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.*;
import com.chaquo.python.PyObject;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

final class ScenarioDesk extends LinearLayout {
    private static final int IMPORT=6901, EXPORT=6902;
    private final TabletActivity host;
    private final Runnable exit;
    private final WebView board;
    private final Button choose, edit, export, cancel, delete, save;
    private String identifier="";
    private int revision;
    private boolean editing,ready;
    private JSONObject payload;

    ScenarioDesk(TabletActivity host,Runnable exit) {
        super(host);
        this.host=host; this.exit=exit;
        setOrientation(VERTICAL);
        LinearLayout bar=new LinearLayout(host);
        addView(bar);
        choose=button(bar,"Scenarios",() -> discardThen(this::chooseScenario));
        choose.setLayoutParams(new LinearLayout.LayoutParams(0,-2,1));
        choose.setMaxLines(1); choose.setEllipsize(android.text.TextUtils.TruncateAt.END);
        edit=button(bar,"Edit",this::toggleEdit);


        board=new WebView(host);
        board.setBackgroundColor(0xff151a1c);
        board.getSettings().setBlockNetworkLoads(true);
        board.getSettings().setAllowContentAccess(false);
        board.getSettings().setJavaScriptEnabled(true);
        board.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView v,String url) {
                if (url.equals("file:///android_asset/battlefield.html")) { ready=true; render(); }
            }
        });
        addView(board,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout footer=new LinearLayout(host);ConsoleSkin.panel(footer,ConsoleSkin.PANEL);addView(footer);
        button(footer,"Import JSON",this::importFile);
        export=button(footer,"Export JSON",this::export);
        footer.addView(new android.view.View(host),new LinearLayout.LayoutParams(0,1,1));
        delete=button(footer,"Delete custom scenario",this::deleteCustom);
        cancel=button(footer,"Cancel editing",this::cancelEdits);
        save=button(footer,"Save",this::toggleEdit);ConsoleSkin.primary(save);
        load(null,false);
        board.loadUrl("file:///android_asset/battlefield.html");
    }
    private Button button(LinearLayout row,String text,Runnable action) {
        Button b=ConsoleSkin.button(host); b.setText(text); b.setOnClickListener(v->action.run()); row.addView(b); return b;
    }
    private void load(String id,boolean editMode) {
        try {
            PyObject data=id==null ? host.read("battlefield") : host.read("battlefield",id);
            payload=new JSONObject(data.toString());
            JSONObject scenario=payload.optJSONObject("scenario");
            identifier=scenario==null ? "" : scenario.optString("id",id==null ? "" : id);
            revision=payload.optInt("revision");
            editing=editMode;
            choose.setText(scenario==null ? "Choose scenario" : scenario.optString("name","").isEmpty() ? "New Scenario" : scenario.getString("name"));
            render();
        } catch (JSONException e) {throw new IllegalStateException(e);}
    }
    private void render() {
        edit.setVisibility(editing?GONE:VISIBLE);
        save.setVisibility(editing?VISIBLE:GONE);
        cancel.setVisibility(editing?VISIBLE:GONE);
        delete.setVisibility(editing && revision>0?VISIBLE:GONE);
        export.setEnabled(!editing && payload.has("scenario"));
        edit.setEnabled(ready && payload.has("scenario"));
        if (ready) board.evaluateJavascript("loadMap("+JSONObject.quote(payload.toString())+","+editing+")",null);
    }
    private void chooseScenario() {
        ArrayList<String> ids=new ArrayList<>(),labels=new ArrayList<>();
        host.scenarioNames().asMap().forEach((k,v)->{ids.add(k.toString()); labels.add(v.toString());});
        ids.add("new"); labels.add("New Scenario");
        ConsoleSkin.dialog(host).setTitle("Battlefield scenario").setItems(labels.toArray(new String[0]),
                (d,i)->load(ids.get(i),ids.get(i).equals("new"))).setNegativeButton("Cancel",null).show();
    }
    private void toggleEdit() {
        if (!editing) { editing=true; render(); return; }
        board.evaluateJavascript("boardDraft()",json->{
            try {
                String id=host.read("save_board",json,identifier,revision).toString();
                load(id,false);
            } catch (RuntimeException e) {error(e);}
        });
    }
    void requestExit() {discardThen(exit);}
    void discardThen(Runnable run) {
        if (!editing) {run.run(); return;}
        ConsoleSkin.dialog(host).setTitle("Discard scenario edits?").setNegativeButton("Keep editing",null)
                .setPositiveButton("Discard",(d,w)->run.run()).show();
    }
    private void importFile(){
        discardThen(()->host.startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),IMPORT));
    }
    private void cancelEdits(){discardThen(()->load(identifier.equals("new")?null:identifier,false));}
    private void deleteCustom(){
        if(!editing || revision<=0)return;
        ConsoleSkin.dialog(host).setTitle("Delete this custom scenario?").setNegativeButton("Cancel",null)
                .setPositiveButton("Delete",(dlg,w)->{
                    try {host.read("delete_board",identifier,revision);load(null,false);}
                    catch(RuntimeException e){error(e);}
                }).show();
    }
    private File pendingExport() {return new File(host.getCacheDir(),"scenario-export.json");}
    private void export() {
        try {
            JSONObject scenario=new JSONObject(payload.getJSONObject("scenario").toString());
            scenario.remove("id");
            try (OutputStream out=new FileOutputStream(pendingExport())) {out.write(scenario.toString(2).getBytes(StandardCharsets.UTF_8));}
            String filename=scenario.getString("name").replaceAll("[^\\p{L}\\p{N} _-]","").trim();
            host.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/json").putExtra(Intent.EXTRA_TITLE,(filename.isEmpty()?"scenario":filename)+".json"),EXPORT);
        } catch (IOException|JSONException|RuntimeException e) {error(e);}
    }
    void fileResult(int request,Uri uri) {
        try {
            if (request==IMPORT) {
                try (InputStream in=host.getContentResolver().openInputStream(uri); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                    if (in==null) throw new IOException("Could not open the selected file.");
                    copy(in,out);
                    load(host.read("save_board",out.toString("UTF-8")).toString(),false);
                }
            } else if (request==EXPORT) {
                try (InputStream in=new FileInputStream(pendingExport()); OutputStream out=host.getContentResolver().openOutputStream(uri,"wt")) {
                    if (out==null) throw new IOException("Could not write to the selected file.");
                    copy(in,out);
                }
                Toast.makeText(host,"Exported scenario",Toast.LENGTH_SHORT).show();
            }
        } catch (IOException|RuntimeException e) {error(e);}
    }
    private void copy(InputStream in,OutputStream out) throws IOException {
        byte[] data=new byte[8192]; int n;
        while ((n=in.read(data))!=-1) out.write(data,0,n);
    }
    private void error(Exception e) {
        ConsoleSkin.dialog(host).setTitle("Scenario could not be saved or opened").setMessage(e.getMessage()).setPositiveButton("OK",null).show();
    }
    void close() { removeView(board); board.destroy(); }
}
