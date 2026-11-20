package app.hangar.prototype;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.TextView;
import com.chaquo.python.PyObject;
import java.io.*;
import java.util.HashMap;
import java.util.List;

final class UnitChoices extends ArrayAdapter<String> {
    private final List<PyObject> units;
    private final HashMap<String,Drawable.ConstantState> icons=new HashMap<>();
    private final TabletActivity host;

    UnitChoices(TabletActivity host,List<PyObject> units,int layout) {
        this(host,units,layout,null);
    }
    UnitChoices(TabletActivity host,List<PyObject> units,int layout,List<String> labels) {
        super(host,layout);
        this.host=host;
        this.units=units;
        if (labels!=null) addAll(labels);
        else for (PyObject unit:units) add(host.playerName(unit.get("player").toInt())+" · "+unit.get("label"));
    }

    private View portrait(View row,int position) {
        TextView name=(TextView)row;
        String id=units.get(position).get("card").get("number").toString();
        if (!icons.containsKey(id)) {
            try (InputStream in=host.getAssets().open("portraits/"+id+".webp")) {
                icons.put(id,Drawable.createFromStream(in,null).getConstantState());
            } catch (IOException e) { throw new IllegalStateException(e); }
        }
        Drawable icon=icons.get(id).newDrawable();
        icon.setBounds(0,0,host.dp(48),host.dp(40));
        name.setCompoundDrawables(icon,null,null,null);
        name.setCompoundDrawablePadding(host.dp(12));
        name.setMinHeight(host.dp(52));
        return name;
    }
    @Override public View getView(int i,View v,ViewGroup parent) {return portrait(super.getView(i,v,parent),i);}
    @Override public View getDropDownView(int i,View v,ViewGroup parent) {return portrait(super.getDropDownView(i,v,parent),i);}
}
