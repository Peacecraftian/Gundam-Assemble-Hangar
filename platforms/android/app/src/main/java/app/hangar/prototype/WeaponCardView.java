package app.hangar.prototype;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.widget.ImageView;
import com.chaquo.python.PyObject;
import java.util.ArrayList;
import java.util.List;

/** Paint and hit-test weapon links in the same fitted card coordinates. */
final class WeaponCardView extends ImageView {
    static final String ATTACK_HINT = "Tap Attacks to Roll";
    private final List<RectF> weapons=new ArrayList<>();
    private final RectF mapped=new RectF();
    private final Paint ink=new Paint(Paint.ANTI_ALIAS_FLAG);
    private int pressedWeapon=-1;

    WeaponCardView(TabletActivity host){super(host);}

    void setWeapons(List<PyObject> attacks){
        weapons.clear();
        for(PyObject attack:attacks)weapons.add(bounds(attack.get("bounds")));
        pressedWeapon=-1;
        invalidate();
    }

    private static RectF bounds(PyObject source){
        List<PyObject> v=source.asList();
        return new RectF(v.get(0).toFloat(),v.get(1).toFloat(),v.get(2).toFloat(),v.get(3).toFloat());
    }

    private RectF onImage(RectF normalized){
        Drawable art=getDrawable();
        mapped.set(normalized);
        mapped.left*=art.getIntrinsicWidth();mapped.right*=art.getIntrinsicWidth();
        mapped.top*=art.getIntrinsicHeight();mapped.bottom*=art.getIntrinsicHeight();
        getImageMatrix().mapRect(mapped);
        mapped.offset(getPaddingLeft(),getPaddingTop());
        return mapped;
    }

    int weaponAt(float x,float y){
        if(getDrawable()!=null)for(int i=0;i<weapons.size();i++)
            if(onImage(weapons.get(i)).contains(x,y))return i;
        return -1;
    }
    boolean hits(PyObject bounds,float x,float y){
        return getDrawable()!=null && onImage(bounds(bounds)).contains(x,y);
    }
    void pressWeapon(int index){
        if(pressedWeapon!=index){pressedWeapon=index;invalidate();}
    }
    @Override protected void onDraw(Canvas canvas){
        super.onDraw(canvas);
        if(getDrawable()==null)return;
        float dp=getResources().getDisplayMetrics().density;
        for(int i=0;i<weapons.size();i++){
            RectF row=onImage(weapons.get(i));
            boolean down=pressedWeapon==i;
            ink.setColor(down?0x71ffb762:0x23ffb762);
            canvas.drawRoundRect(row,2*dp,2*dp,ink);
            // A dark backing keeps the amber underline visible on pale printed cards.
            float h=Math.min(row.height()*.16f,(down?3:2)*dp);
            ink.setColor(0xff59432c);canvas.drawRect(row.left,row.bottom-h-dp*.6f,row.right,row.bottom,ink);
            ink.setColor(down?0xffffdda8:ConsoleSkin.AMBER);
            canvas.drawRect(row.left,row.bottom-h,row.right,row.bottom,ink);
        }
    }
}
