package app.hangar.prototype;

import android.app.Activity;
import android.app.Dialog;
import android.content.Intent;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;


import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import org.json.JSONObject;
import org.json.JSONException;
import java.io.*;
import java.text.Normalizer;
import java.util.*;

public final class TacticsActivity extends Activity {
    private static final class Card {
        final String number, name, search;
        Card(String number, String name) {
            this.number = number;
            this.name = name;
            search = normalize(name) + " " + normalize(number);
        }
    }

    private final ArrayList<Card> catalog = new ArrayList<>();
    private final ArrayList<Card> matches = new ArrayList<>();
    private final android.util.LruCache<String, Bitmap> thumbnails =
            new android.util.LruCache<String, Bitmap>(6 * 1024 * 1024) {
                @Override protected int sizeOf(String key, Bitmap bmp) { return bmp.getAllocationByteCount(); }
            };
    private GridView grid;
    private FrameLayout center;
    private LinearLayout preview;
    private Card drawn;
    private final ScrollView[] rails=new ScrollView[2];
    private EditText search;
    private TextView count;
    private Button clear;
    private Card open;
    private Typeface heading;
    private final Cards adapter = new Cards();

    private static String normalize(String text) {
        return Normalizer.normalize(text, Normalizer.Form.NFKD)
                .replaceAll("\\p{M}+", "").replace('’', '\'').toLowerCase(Locale.ROOT).trim();
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        heading = Typeface.createFromAsset(getAssets(), "ChakraPetch-Bold.ttf");
        try (BufferedReader in = new BufferedReader(new InputStreamReader(getAssets().open("tactics.json"), "UTF-8"))) {
            StringBuilder json = new StringBuilder();
            String line;
            while ((line = in.readLine()) != null) json.append(line);
            JSONObject cards = new JSONObject(json.toString());
            Iterator<String> it = cards.keys();
            while (it.hasNext()) {
                String id = it.next();
                catalog.add(new Card(id, cards.getString(id)));
            }
        } catch (IOException | JSONException e) { throw new IllegalStateException(e); }
        catalog.sort(Comparator.comparing(c -> c.number));
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setFocusableInTouchMode(true);
        ConsoleSkin.background(page);
        page.setOnApplyWindowInsetsListener((v,i) -> {
            v.setPadding(dp(12)+i.getSystemWindowInsetLeft(),dp(4)+i.getSystemWindowInsetTop(),
                    dp(12)+i.getSystemWindowInsetRight(),dp(4)+i.getSystemWindowInsetBottom());
            return i;
        });
        setContentView(page);
        page.addView(ConsoleSkin.header(this,3,getIntent().getBooleanExtra("match",false),tab->{
            setResult(RESULT_OK,new Intent().putExtra("tab",tab));finish();
        }));
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        page.addView(bar);
        TextView title = new TextView(this);
        title.setText("Tactics");
        title.setTypeface(heading);
        title.setTextSize(23);
        title.setPadding(0,0,dp(14),0);
        bar.addView(title);
        search = new EditText(this);
        search.setHint("Search by name or card number");
        search.setSingleLine(true);
        search.setInputType(InputType.TYPE_CLASS_TEXT);
        search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        bar.addView(search, new LinearLayout.LayoutParams(0,dp(52),1));
        clear = button("Clear", () -> search.setText(""));
        bar.addView(clear);
        bar.addView(button("Back", this::finish));
        count = new TextView(this);
        count.setPadding(dp(4),dp(2),0,dp(6));
        count.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        page.addView(count);
        grid = new GridView(this);
        grid.setNumColumns(GridView.AUTO_FIT);
        grid.setColumnWidth(dp(154));
        grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);
        grid.setVerticalSpacing(dp(8));
        grid.setHorizontalSpacing(dp(8));
        LinearLayout desk=new LinearLayout(this);page.addView(desk,new LinearLayout.LayoutParams(-1,0,1));
        addRail(desk,0);
        center=new FrameLayout(this);desk.addView(center,new LinearLayout.LayoutParams(0,-1,1));
        center.addView(grid,-1,-1);
        addRail(desk,1);
        grid.setAdapter(adapter);
        grid.setOnItemClickListener((p,v,pos,id) -> showCard(matches.get(pos)));
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s,int start,int count,int after) {}
            public void onTextChanged(CharSequence s,int start,int before,int count) { filter(); }
            public void afterTextChanged(Editable e) {}
        });
        search.setOnEditorActionListener((v,action,event) -> {
            if (action != EditorInfo.IME_ACTION_SEARCH) return false;
            hideKeyboard();
            if (!matches.isEmpty()) showCard(matches.get(0));
            return true;
        });
        if(state!=null) for(int side=0;side<2;side++){
            final int lane=side; rails[lane].post(()->rails[lane].scrollTo(0,state.getInt("rail"+lane)));
        }
        search.setText(state == null ? "" : state.getString("query",""));
        if (state != null) {
            grid.setSelection(state.getInt("position"));
            for(Card c:catalog) if(c.number.equals(state.getString("drawn"))) draw(c,0);
            for (Card c : catalog) if (c.number.equals(state.getString("card"))) showCard(c);
        }
    }
    private void filter() {
        returnCard();
        String query = normalize(search.getText().toString());
        matches.clear();
        for (Card c : catalog) if (c.search.contains(query)) matches.add(c);
        adapter.notifyDataSetChanged();
        grid.setSelection(0);
        clear.setEnabled(search.length()>0);
        count.setText(matches.isEmpty() ? "No cards match this search" :
                matches.size() + (matches.size()==1 ? " card" : " cards"));
    }
    private Bitmap thumbnail(Card c) {
        Bitmap b=thumbnails.get(c.number);
        if(b==null){b=decode(c,4);thumbnails.put(c.number,b);}
        return b;
    }
    private void addRail(LinearLayout desk,int side){
        ScrollView rail=new ScrollView(this);rails[side]=rail;
        rail.setClipToPadding(false);rail.setPadding(dp(9),dp(8),dp(9),dp(8));
        int width=getResources().getConfiguration().screenWidthDp>=1000?124:86;
        desk.addView(rail,dp(width),-1);
        LinearLayout fan=new LinearLayout(this);fan.setOrientation(LinearLayout.VERTICAL);
        fan.setClipChildren(false);rail.addView(fan);
        for(int i=side;i<catalog.size();i+=2){
            Card c=catalog.get(i);
            ImageButton tile=new ImageButton(this);tile.setPadding(0,0,0,0);tile.setBackgroundColor(0);
            tile.setImageBitmap(thumbnail(c));tile.setScaleType(ImageView.ScaleType.FIT_CENTER);
            tile.setRotation(side==0?-9:9);tile.setContentDescription("Draw "+c.name+" · "+c.number);
            tile.setOnClickListener(v->draw(c,side==0?-1:1));
            LinearLayout.LayoutParams slot=new LinearLayout.LayoutParams(-1,dp((width-18)*14/10));
            if(i>=2)slot.topMargin=-dp(Math.round((width-18)*.73f));
            fan.addView(tile,slot);
        }
    }
    private void draw(Card c,int side){
        hideKeyboard();returnCard();drawn=c;grid.setVisibility(View.GONE);
        preview=new LinearLayout(this);preview.setOrientation(LinearLayout.VERTICAL);
        ImageView image=new ImageView(this);image.setImageBitmap(decode(c,1));
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);image.setContentDescription(c.name+" drawn card");
        image.setOnClickListener(v->showCard(c));
        preview.addView(image,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout tools=new LinearLayout(this);tools.setGravity(Gravity.CENTER);
        tools.addView(button("Return to fan",this::returnCard));
        tools.addView(button("View card",()->showCard(c)));
        preview.addView(tools);center.addView(preview,-1,-1);
        image.setTranslationX(side*center.getWidth()*.4f);image.setRotation(side*8);image.setScaleX(.8f);image.setScaleY(.8f);
        image.animate().translationX(0).rotation(0).scaleX(1).scaleY(1).setDuration(300).start();
    }
    private void returnCard(){
        if(preview==null)return;
        center.removeView(preview);preview=null;drawn=null;grid.setVisibility(View.VISIBLE);
    }
    @Override public void onBackPressed(){if(drawn!=null)returnCard();else super.onBackPressed();}
    private void hideKeyboard() {
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(search.getWindowToken(),0);
        search.clearFocus();
    }
    private Bitmap decode(Card c,int sample) {
        try (InputStream in = getAssets().open("tactics/"+c.number+".webp")) {
            BitmapFactory.Options opts = new BitmapFactory.Options();
            opts.inSampleSize = sample;
            return BitmapFactory.decodeStream(in,null,opts);
        } catch(IOException e) { throw new IllegalStateException(e); }
    }
    private final class Cards extends BaseAdapter {
        public int getCount() { return matches.size(); }
        public Card getItem(int pos) { return matches.get(pos); }
        public long getItemId(int pos) { return pos; }
        public View getView(int pos,View recycled,ViewGroup parent) {
            LinearLayout tile = (LinearLayout)recycled;
            if (tile == null) {
                tile = new LinearLayout(TacticsActivity.this);
                tile.setOrientation(LinearLayout.VERTICAL);
                tile.setPadding(dp(6),dp(6),dp(6),dp(6));
                tile.setBackgroundColor(0xff242c2e);
                ImageView image = new ImageView(TacticsActivity.this);
                image.setScaleType(ImageView.ScaleType.FIT_CENTER);
                tile.addView(image,-1,dp(150));
                TextView title = new TextView(TacticsActivity.this);
                title.setTypeface(heading); title.setTextSize(16);
                title.setMinLines(2); title.setMaxLines(2);
                tile.addView(title);
                TextView code = new TextView(TacticsActivity.this);
                code.setTextColor(0xffffb762);
                tile.addView(code);
            }
            Card c = getItem(pos);
            ((ImageView)tile.getChildAt(0)).setImageBitmap(thumbnail(c));
            ((TextView)tile.getChildAt(1)).setText(c.name);
            ((TextView)tile.getChildAt(2)).setText(c.number);
            tile.setContentDescription(c.name+" · "+c.number);
            return tile;
        }
    }

    private Button button(String name,Runnable action) {
        Button b = ConsoleSkin.button(this);
        b.setText(name); b.setMinHeight(dp(48)); b.setOnClickListener(v -> action.run());
        return b;
    }
    private void showCard(Card c) {
        hideKeyboard();
        open = c;
        Dialog dialog = new Dialog(this,android.R.style.Theme_Material_NoActionBar_Fullscreen);
        LinearLayout page = new LinearLayout(this);
        ConsoleSkin.background(page);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(12),dp(4),dp(12),dp(4));
        page.setFitsSystemWindows(true);
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL); page.addView(bar);
        TextView title = new TextView(this);
        title.setText(c.name+" · "+c.number);
        title.setTextSize(18); title.setTypeface(heading);
        bar.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        ImageView art = new ImageView(this);
        art.setScaleType(ImageView.ScaleType.FIT_CENTER);
        art.setContentDescription(c.name+" full card");
        Bitmap bmp = decode(c,1);
        art.setImageBitmap(bmp);
        FrameLayout frame = new FrameLayout(this);
        frame.addView(art,-1,-1);
        scroll.addView(frame);
        Button zoom = ConsoleSkin.button(this);
        zoom.setText("Enlarge"); zoom.setMinHeight(dp(48));
        zoom.setOnClickListener(v -> {
            boolean enlarge = art.getLayoutParams().height == -1;
            int height = enlarge ? Math.round(scroll.getWidth() * bmp.getHeight() / (float)bmp.getWidth()) : -1;
            art.setLayoutParams(new FrameLayout.LayoutParams(-1,height));
            scroll.scrollTo(0,0); zoom.setText(enlarge ? "Fit card" : "Enlarge");
        });
        int index=matches.indexOf(c);
        Button previous=button("Previous",()->{ dialog.dismiss(); showCard(matches.get(index-1)); });
        Button next=button("Next",()->{ dialog.dismiss(); showCard(matches.get(index+1)); });
        previous.setEnabled(index>0);
        next.setEnabled(index>=0 && index+1<matches.size());
        bar.addView(previous);
        bar.addView(next);
        bar.addView(zoom);
        bar.addView(button("Close card",dialog::dismiss));
        page.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        dialog.setContentView(page);
        dialog.setOnDismissListener(d -> {if (open==c) open=null;});
        dialog.show();
    }
    @Override protected void onResume() {
        super.onResume();
        TabletDisplay.apply(this);
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        for(int i=0;i<rails.length;i++)state.putInt("rail"+i,rails[i].getScrollY());
        if(drawn!=null)state.putString("drawn",drawn.number);
        state.putString("query",search.getText().toString());
        state.putInt("position",grid.getFirstVisiblePosition());
        if (open!=null) state.putString("card",open.number);
    }
}
