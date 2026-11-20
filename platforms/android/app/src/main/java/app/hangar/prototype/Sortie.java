package app.hangar.prototype;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import java.io.InputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;
import android.text.InputType;
import android.view.Gravity;
import android.widget.*;
import com.chaquo.python.PyException;
import com.chaquo.python.PyObject;
import org.json.JSONArray;
import java.util.ArrayList;
import java.util.List;

final class Sortie extends LinearLayout {
    private final Activity activity;
    private final Set<String> fullArt = new HashSet<>();
    private final HashMap<String,Bitmap> thumbnails = new HashMap<>();
    private final PyObject session;
    private final Typeface font;
    private final Runnable onStart;
    private final List<PyObject> cards;
    private final List<List<String>> squads = new ArrayList<>();
    private final EditText[] names = new EditText[2];
    private final LinearLayout[] lists = new LinearLayout[2];
    private final ArrayList<String> scenarioIds = new ArrayList<>();
    private final Spinner scenario;
    private final NumberPicker phases;
    private final Button start;
    private final boolean saved;

    Sortie(Activity activity, PyObject session, Typeface font, Runnable onStart, Runnable resume) {
        super(activity);
        this.activity = activity;
        this.session = session;
        try {
            fullArt.addAll(Arrays.asList(activity.getAssets().list("sortie")));
        } catch (IOException e) {
            throw new IllegalStateException("Could not read the Sortie art catalog", e);
        }
        this.font = font;
        this.onStart = onStart;
        saved = session.get("match") != null;
        cards = new ArrayList<>(session.get("catalog").asMap().values());
        cards.sort((a,b) -> a.get("name").toString().compareToIgnoreCase(b.get("name").toString()));
        ConsoleSkin.background(this);
        setOrientation(VERTICAL);
        setFocusableInTouchMode(true);
        setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(dp(16)+insets.getSystemWindowInsetLeft(),dp(8)+insets.getSystemWindowInsetTop(),
                    dp(16)+insets.getSystemWindowInsetRight(),dp(8)+insets.getSystemWindowInsetBottom());
            return insets;
        });
        addView(((TabletActivity)activity).header(0));
        LinearLayout options = new LinearLayout(activity);
        options.setGravity(Gravity.CENTER_VERTICAL);
        addView(options);
        options.addView(text("Scenario", 16));
        ArrayList<String> missions = new ArrayList<>();
        missions.add("No scenario");
        scenarioIds.add("");
        session.get("scenarios").asMap().forEach((id,name) -> {
            scenarioIds.add(id.toString()); missions.add(name.toString());
        });
        scenario = new Spinner(activity, Spinner.MODE_DIALOG);
        scenario.setContentDescription("Choose scenario");
        scenario.setAdapter(new ArrayAdapter<>(activity, android.R.layout.simple_spinner_dropdown_item, missions));
        options.addView(scenario, new LayoutParams(0,dp(52),1));
        options.addView(text("Phases",16));
        phases = new NumberPicker(activity);
        phases.setMinValue(1);
        phases.setMaxValue(99);
        phases.setValue(2);
        phases.setDescendantFocusability(FOCUS_BLOCK_DESCENDANTS);
        options.addView(phases,dp(72),dp(88));
        LinearLayout columns = new LinearLayout(activity);
        addView(columns,new LayoutParams(-1,0,1));
        if(getResources().getConfiguration().screenWidthDp>=900) catalogPanel(columns);
        for (int side=0;side<2;side++) buildSquad(columns,side);
        LinearLayout footer = new LinearLayout(activity);
        footer.setGravity(Gravity.END);
        Button fullscreen=button(TabletDisplay.label(activity),()->{});
        fullscreen.setOnClickListener(v->{TabletDisplay.toggle(activity); fullscreen.setText(TabletDisplay.label(activity));});
        footer.addView(fullscreen);

        addView(footer);
        if (saved) footer.addView(button("Resume match",resume));
        start = button("Start match",this::confirmStart);
        ConsoleSkin.primary(start);
        footer.addView(start);
        updateStart();
    }

    void refreshScenarios() {
        String selected=scenarioIds.get(scenario.getSelectedItemPosition());
        scenarioIds.clear(); scenarioIds.add("");
        ArrayList<String> labels=new ArrayList<>(); labels.add("No scenario");
        session.get("scenarios").asMap().forEach((id,name) -> {
            scenarioIds.add(id.toString()); labels.add(name.toString());
        });
        scenario.setAdapter(new ArrayAdapter<>(activity,android.R.layout.simple_spinner_dropdown_item,labels));
        scenario.setSelection(Math.max(0,scenarioIds.indexOf(selected)));
    }

    private void buildSquad(LinearLayout columns, int side) {
        squads.add(new ArrayList<>());
        LinearLayout panel = new LinearLayout(activity);
        panel.setOrientation(VERTICAL);
        ConsoleSkin.panel(panel,ConsoleSkin.HOUSING[side]);
        panel.setPadding(dp(8),dp(4),dp(8),dp(4));
        LayoutParams column = new LayoutParams(0,-1,1);
        column.setMargins(dp(3),0,dp(3),dp(4));
        columns.addView(panel,column);
        String team = side==0 ? "Blue" : "Red";
        EditText name = new EditText(activity);
        name.setSingleLine(true);
        name.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS);
        name.setText(team);
        name.setSelectAllOnFocus(true);
        name.setContentDescription(team+" player name");
        names[side]=name;
        panel.addView(name);
        panel.addView(button("Add unit to "+team,() -> chooseCard(side,squads.get(side).size())));
        ScrollView scroll = new ScrollView(activity);
        panel.addView(scroll,new LayoutParams(-1,0,1));
        lists[side] = new LinearLayout(activity);
        lists[side].setOrientation(VERTICAL);
        scroll.setFillViewport(true);scroll.addView(lists[side]);
        enableDrop(scroll,side);
    }

    private void catalogPanel(LinearLayout columns){
        LinearLayout catalog=new LinearLayout(activity);catalog.setOrientation(VERTICAL);
        ConsoleSkin.panel(catalog,ConsoleSkin.PANEL);catalog.setPadding(dp(6),dp(4),dp(6),dp(4));
        LayoutParams p=new LayoutParams(0,-1,1.1f);p.setMargins(dp(3),0,dp(3),dp(4));columns.addView(catalog,p);
        catalog.addView(ConsoleSkin.title(activity,"Unit Catalog",19));
        EditText search=new EditText(activity);search.setSingleLine(true);search.setHint("Search published units");catalog.addView(search);
        ScrollView scroll=new ScrollView(activity);catalog.addView(scroll,new LayoutParams(-1,0,1));
        LinearLayout rows=new LinearLayout(activity);rows.setOrientation(VERTICAL);scroll.addView(rows);
        for(PyObject card:cards){
            String number=card.get("number").toString();
            TextView tile=text(card.get("name")+"\n"+number,15);
            tile.setGravity(Gravity.CENTER_VERTICAL);tile.setMinHeight(dp(54));tile.setPadding(dp(5),0,dp(5),0);
            portrait(tile,card);rows.addView(tile);
            tile.setTag(normalize(card.get("name")+" "+card.get("title")+" "+number));
            tile.setContentDescription("Catalog "+card.get("name")+" "+number);
            tile.setOnClickListener(v->viewCard(card));
            tile.setOnLongClickListener(v->v.startDragAndDrop(null,new android.view.View.DragShadowBuilder(v),number,0));
        }
        search.addTextChangedListener(new android.text.TextWatcher(){
            public void beforeTextChanged(CharSequence s,int a,int c,int n){}
            public void onTextChanged(CharSequence s,int a,int b,int c){
                String q=normalize(s.toString());
                for(int i=0;i<rows.getChildCount();i++){
                    android.view.View item=rows.getChildAt(i);
                    item.setVisibility(item.getTag().toString().contains(q)?VISIBLE:GONE);
                }
            }
            public void afterTextChanged(android.text.Editable s){}
        });
    }

    private void enableDrop(ScrollView scroll,int side){
        LinearLayout list=lists[side];
        android.graphics.drawable.ColorDrawable line=new android.graphics.drawable.ColorDrawable(ConsoleSkin.AMBER);
        scroll.setOnDragListener((v,event)->{
            Object drag=event.getLocalState();
            if(!(drag instanceof String) && (!(drag instanceof int[]) || ((int[])drag)[0]!=side)) return false;
            List<String> squad=squads.get(side);
            switch(event.getAction()){
                case android.view.DragEvent.ACTION_DRAG_STARTED:return true;
                case android.view.DragEvent.ACTION_DRAG_LOCATION:
                case android.view.DragEvent.ACTION_DROP:
                    float y=event.getY();int slot=0;
                    while(slot<list.getChildCount()){
                        android.view.View row=list.getChildAt(slot);
                        if(y+scroll.getScrollY()<row.getTop()+row.getHeight()*.5f)break;
                        slot++;
                    }
                    if(event.getAction()==android.view.DragEvent.ACTION_DROP){
                        list.getOverlay().remove(line);
                        if(drag instanceof String){
                            String number=(String)drag;PyObject card=session.get("catalog").asMap().get(PyObject.fromJava(number));
                            if(squad.contains(number) && !card.get("mass_produced").toBoolean())
                                Toast.makeText(activity,"Only Mass Produced units may be duplicated.",Toast.LENGTH_SHORT).show();
                            else {squad.add(slot,number);drawSquad(side);}
                        } else {int from=((int[])drag)[1];moveSlot(side,from,slot>from?slot-1:slot);}
                    }else{
                        int top=slot==0?0:list.getChildAt(slot-1).getBottom()-dp(2);
                        line.setBounds(0,top,list.getWidth(),top+dp(3));list.getOverlay().add(line);
                        if(y<dp(24))scroll.scrollBy(0,-dp(5));else if(y>scroll.getHeight()-dp(24))scroll.scrollBy(0,dp(5));
                    }
                    return true;
                case android.view.DragEvent.ACTION_DRAG_EXITED:
                case android.view.DragEvent.ACTION_DRAG_ENDED:list.getOverlay().remove(line);return true;
                default:return true;
            }
        });
    }

    private void chooseCard(int side,int insertAt) {
        List<String> squad = squads.get(side);
        ArrayList<PyObject> available = new ArrayList<>();
        ArrayList<String> labels = new ArrayList<>();
        for (PyObject card : cards) {
            String number = card.get("number").toString();
            if (!card.get("mass_produced").toBoolean() && squad.contains(number)) continue;
            available.add(card);
            labels.add(card.get("name")+" · "+card.get("title")+" · "+number);
        }
        LinearLayout panel=new LinearLayout(activity);
        panel.setOrientation(VERTICAL);
        panel.setFocusableInTouchMode(true);
        EditText search=new EditText(activity);
        search.setSingleLine(); search.setHint("Search Units by name, title or card number");
        panel.addView(search);
        ListView list=new ListView(activity);
        panel.addView(list,new LayoutParams(-1,dp(280)));
        ArrayList<Integer> hits=new ArrayList<>();
        ArrayAdapter<String> adapter=new ArrayAdapter<String>(activity,android.R.layout.simple_list_item_1) {
            @Override public android.view.View getView(int pos,android.view.View recycled,android.view.ViewGroup parent) {
                LinearLayout row=recycled instanceof LinearLayout ? (LinearLayout)recycled : null;
                if (row==null) {
                    row=new LinearLayout(activity);
                    row.setGravity(Gravity.CENTER_VERTICAL);
                    TextView item=text("",16); row.addView(item,new LayoutParams(0,-2,1));
                    Button inspect=button("View card",()->{});
                    inspect.setFocusable(false);
                    row.addView(inspect);
                    row.setPadding(dp(8),0,dp(4),0);
                }
                PyObject card=available.get(hits.get(pos));
                TextView item=(TextView)row.getChildAt(0);
                item.setText(getItem(pos)); portrait(item,card);
                Button inspect=(Button)row.getChildAt(1);
                inspect.setContentDescription("View "+card.get("name")+" "+card.get("number"));
                inspect.setOnClickListener(v->viewCard(card));
                return row;
            }
        };
        list.setAdapter(adapter);
        Runnable filter=()->{
            String q=normalize(search.getText().toString());
            hits.clear(); adapter.clear();
            for(int i=0;i<labels.size();i++) if(normalize(labels.get(i)).contains(q)) {
                hits.add(i); adapter.add(labels.get(i));
            }
            adapter.notifyDataSetChanged();
        };
        search.addTextChangedListener(new android.text.TextWatcher(){
            public void beforeTextChanged(CharSequence s,int a,int c,int n){}
            public void onTextChanged(CharSequence s,int a,int b,int c){filter.run();}
            public void afterTextChanged(android.text.Editable s){}
        });
        filter.run();
        AlertDialog dialog=ConsoleSkin.dialog(activity).setTitle("Unit Catalog").setView(panel).setNegativeButton("Cancel",null).create();
        list.setOnItemClickListener((parent,v,pos,id)->{
            squad.add(insertAt,available.get(hits.get(pos)).get("number").toString());
            drawSquad(side); dialog.dismiss();
        });
        dialog.show();
    }

    private String normalize(String label) {
        return java.text.Normalizer.normalize(label,java.text.Normalizer.Form.NFKD)
                .replaceAll("\\p{M}+","").replace("’","'").trim().toLowerCase(java.util.Locale.ROOT);
    }

    private String sortieImage(PyObject card) {
        String name = card.get("number").toString() + ".webp";
        return fullArt.contains(name) ? "sortie/" + name : card.get("image").toString();
    }

    private void viewCard(PyObject card) {
        new ConsoleMenus((TabletActivity)activity).displayCard(card, false, sortieImage(card));
    }

    private void portrait(TextView label, PyObject card) {
        String path = sortieImage(card);
        Bitmap thumbnail = thumbnails.get(path);
        if (thumbnail == null) {
            try (InputStream image = activity.getAssets().open(path)) {
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inSampleSize = 4;
                thumbnail = BitmapFactory.decodeStream(image, null, options);
            } catch (IOException e) {
                throw new IllegalStateException(path, e);
            }
            if (thumbnail == null) throw new IllegalStateException("Unreadable card: " + path);
            thumbnails.put(path, thumbnail);
        }
        BitmapDrawable icon = new BitmapDrawable(getResources(), thumbnail);
        int height = dp(44);
        icon.setBounds(0, 0, Math.round(height * thumbnail.getWidth() / (float)thumbnail.getHeight()), height);
        label.setCompoundDrawables(icon,null,null,null);
        label.setCompoundDrawablePadding(dp(8));
    }
    private void moveSlot(int side,int from,int to) {
        List<String> squad=squads.get(side);
        if(to>=0 && to<squad.size() && from!=to) { squad.add(to,squad.remove(from)); drawSquad(side); }
    }

    private void drawSquad(int side) {
        LinearLayout list = lists[side];
        list.removeAllViews();
        List<String> squad=squads.get(side);
        for (int index=0; index<squad.size(); index++) {
            final int slot=index;
            String number=squad.get(index);
            PyObject card=session.get("catalog").asMap().get(PyObject.fromJava(number));
            LinearLayout row = new LinearLayout(activity);
            row.setGravity(Gravity.CENTER_VERTICAL);
            list.addView(row);
            TextView label=text("#"+(slot+1)+"  "+card.get("name")+" · "+number,16);
            portrait(label,card);
            row.addView(label,new LayoutParams(0,-2,1));
            label.setMinHeight(dp(52)); label.setGravity(Gravity.CENTER_VERTICAL);
            label.setOnClickListener(v->ConsoleSkin.dialog(activity).setTitle(card.get("name").toString())
                    .setItems(new String[]{"Insert unit before","Move earlier","Move later","View card"},(d,i)->{
                        if(i==0) chooseCard(side,slot);
                        else if(i==3) viewCard(card);
                        else moveSlot(side,slot,slot+(i==1?-1:1));
                    }).setNegativeButton("Cancel",null).show());
            label.setOnLongClickListener(v->v.startDragAndDrop(null,new android.view.View.DragShadowBuilder(row),new int[]{side,slot},0));
            Button remove=button("−",() -> { squad.remove(slot); drawSquad(side); });
            remove.setMinWidth(dp(48));
            remove.setMinimumWidth(dp(48));
            remove.setContentDescription("Remove "+(side==0?"Blue":"Red")+" slot "+(slot+1));
            row.addView(remove);
        }
        updateStart();
    }

    private void updateStart() { start.setEnabled(!squads.get(0).isEmpty() && !squads.get(1).isEmpty()); }
    private void confirmStart() {
        for (EditText name : names) if (name.getText().toString().trim().isEmpty()) {
            name.setError("Enter a player name"); name.requestFocus(); return;
        }
        if (saved) ConsoleSkin.dialog(activity).setTitle("Replace saved match?")
                .setMessage("Starting this match replaces the saved match and its undo history.")
                .setNegativeButton("Cancel",null).setPositiveButton("Start match",(d,w)->startMatch()).show();
        else startMatch();
    }
    private void startMatch() {
        try {
            session.callAttr("start",names[0].getText().toString(),names[1].getText().toString(),
                    phases.getValue(),scenarioIds.get(scenario.getSelectedItemPosition()),new JSONArray(squads).toString());
        } catch (PyException e) {
            ConsoleSkin.dialog(activity).setMessage(e.getMessage()).setPositiveButton("OK",null).show();
            return;
        }
        onStart.run();
    }
    private TextView text(String value,int size) {
        TextView label = new TextView(activity);
        label.setTypeface(font); label.setTextSize(size); label.setText(value);
        return label;
    }
    private Button button(String label,Runnable click) {
        Button b = ConsoleSkin.button(activity);
        b.setText(label); b.setMinHeight(dp(48)); b.setOnClickListener(v -> click.run());
        return b;
    }
    private int dp(int n) { return Math.round(n*getResources().getDisplayMetrics().density); }
}
