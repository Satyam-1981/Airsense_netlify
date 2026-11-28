"""Train a 3-hourly AtmoIQ RF/GB/KNN ensemble on Open-Meteo historical AQ data.

Important: targets are CPCB-breakpoint-derived proxy AQI labels from CAMS Global modelled
concentrations, NOT ground-truth CPCB station AQI observations. CAMS Global
currently does not provide ammonia (NH3), so this proxy excludes NH3.
"""
from __future__ import annotations
import json, os, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import requests
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, accuracy_score
import joblib
from dotenv import load_dotenv

BASE=Path(__file__).parent
ROOT=BASE.parent
load_dotenv(ROOT/".env")

def output_path(env_name, default):
    value=Path(os.getenv(env_name, str(default))).expanduser()
    return value if value.is_absolute() else (ROOT/value).resolve()

ARTIFACT_PATH=output_path("ML_ARTIFACT_PATH", BASE/"artifacts"/"atmoiq_models.joblib")
METRICS_PATH=output_path("ML_METRICS_PATH", BASE/"artifacts"/"metrics.json")
FEATURES=["pm2_5","pm10","nitrogen_dioxide","sulphur_dioxide","carbon_monoxide","ozone"]
CITIES={"Kolkata":(22.5726,88.3639),"Howrah":(22.5958,88.2636),"Durgapur":(23.5204,87.3119),"Asansol":(23.6739,86.9524),"Siliguri":(26.7271,88.3953),"Haldia":(22.0667,88.0698),"Deoghar":(24.4854,86.6947),"Delhi":(28.6139,77.2090),"Mumbai":(19.0760,72.8777),"Bengaluru":(12.9716,77.5946),"Chennai":(13.0827,80.2707),"Hyderabad":(17.3850,78.4867)}
# (low, high, AQI-low, AQI-high); concentrations in µg/m³ except CO mg/m³.
BP={"pm2_5":[(0,30,0,50),(30,60,50,100),(60,90,100,200),(90,120,200,300),(120,250,300,400),(250,500,401,500)],"pm10":[(0,50,0,50),(50,100,50,100),(100,250,100,200),(250,350,200,300),(350,430,300,400),(430,600,401,500)],"nitrogen_dioxide":[(0,40,0,50),(40,80,50,100),(80,180,100,200),(180,280,200,300),(280,400,300,400),(400,1000,401,500)],"sulphur_dioxide":[(0,40,0,50),(40,80,50,100),(80,380,100,200),(380,800,200,300),(800,1600,300,400),(1600,2000,401,500)],"carbon_monoxide":[(0,1,0,50),(1,2,50,100),(2,10,100,200),(10,17,200,300),(17,34,300,400),(34,50,401,500)],"ozone":[(0,50,0,50),(50,100,50,100),(100,168,100,200),(168,208,200,300),(208,748,300,400),(748,1000,401,500)]}
def sub_index(name,value):
    if pd.isna(value) or value < 0: return np.nan
    for lo,hi,ilo,ihi in BP[name]:
        if lo<=value<=hi: return (ihi-ilo)*(value-lo)/(hi-lo)+ilo
    return 500.0 if value>0 else 0.0

def fetch_city(name,coords,start,end):
    lat,lon=coords; url="https://air-quality-api.open-meteo.com/v1/air-quality"
    params={"latitude":lat,"longitude":lon,"hourly":",".join(FEATURES),"start_date":start,"end_date":end,"timezone":"UTC","domains":"cams_global"}
    last_error=None
    for attempt in range(3):
        try:
            r=requests.get(url,params=params,timeout=120); r.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error=exc
            if attempt==2: raise
            time.sleep(2**attempt)
    else:
        raise RuntimeError(f"Open-Meteo request failed for {name}: {last_error}")
    data=r.json(); h=data.get("hourly",{})
    if not h.get("time"): raise RuntimeError(f"No forecast data for {name}: {data}")
    df=pd.DataFrame(h)
    df["time"]=pd.to_datetime(df["time"],utc=True)
    intervals=df["time"].diff().dropna().dt.total_seconds()/3600
    median_interval=float(intervals.median()) if len(intervals) else 0
    if median_interval <= 1.5:
        # Open-Meteo can expose interpolated hourly values for a 3-hour model.
        # Retain only UTC 00/03/06/... native model timestamps.
        df=df[(df["time"].dt.minute==0) & (df["time"].dt.hour%3==0)].copy()
    elif median_interval > 3.5:
        raise RuntimeError(f"Unexpected CAMS Global time step ({median_interval:.1f} hours); no values were interpolated.")
    if len(df)<2: raise RuntimeError(f"No native 3-hour CAMS Global points for {name}; interpolated hourly values were not used.")
    # Keep UTC as naive timestamps for pandas' chronological split; reindex to
    # a regular 3-hour grid and leave gaps NaN rather than filling them.
    df["time"]=df["time"].dt.tz_convert(None)
    grid=pd.date_range(start=df["time"].iloc[0],end=df["time"].iloc[-1],freq="3h")
    df=df.set_index("time").reindex(grid).rename_axis("time").reset_index()
    df["city"]=name
    return df

def build_targets(df):
    # CAMS Global is native 3-hourly. Use 8 points for a 24-hour mean (minimum
    # 6 valid points); approximate CPCB's 8-hour CO/O3 window with 3 samples.
    df=df.sort_values(["city","time"]).copy()
    for col in FEATURES:
        df[col]=pd.to_numeric(df[col],errors="coerce")
        df[col]=df[col].where(np.isfinite(df[col]) & (df[col]>=0))
    df["carbon_monoxide"]=df["carbon_monoxide"]/1000.0 # Open-Meteo µg/m³ -> mg/m³
    full_24h_window=df.groupby("city").cumcount()>=7
    for col in ["pm2_5","pm10","nitrogen_dioxide","sulphur_dioxide"]:
        rolling_mean=df.groupby("city")[col].transform(lambda s:s.rolling(8,min_periods=6).mean())
        df[f"avg_{col}"]=rolling_mean.where(full_24h_window)
    for col in ["carbon_monoxide","ozone"]:
        grouped=df.groupby("city")[col]
        approx_eight_hour=grouped.transform(lambda s:s.rolling(3,min_periods=3).mean())
        max_approx=approx_eight_hour.groupby(df["city"]).transform(lambda s:s.rolling(6,min_periods=1).max())
        valid_24=grouped.transform(lambda s:s.rolling(8,min_periods=1).count())
        df[f"avg_{col}"]=max_approx.where((valid_24>=6)&full_24h_window)
    subs=pd.DataFrame({k:df[f"avg_{k}"].map(lambda x:sub_index(k,x)) for k in FEATURES})
    # Operational minimum: at least 3 valid sub-indices including one particulate.
    count=subs.notna().sum(axis=1)
    particulate=subs[["pm2_5","pm10"]].notna().any(axis=1)
    df["aqi"]=subs.max(axis=1); df.loc[(count<3)|(~particulate),"aqi"]=np.nan
    return 

def main():
    default_end=(date.today()-timedelta(days=2)).isoformat()
    start=os.getenv("START_DATE","2022-08-01"); end=os.getenv("END_DATE",default_end)
    # Bound memory on small hosting plans: calculate rolling features for one
    # city at a time, then sample that city's valid rows before retaining it.
    # Rolling windows are computed before sampling, so the features preserve
    # their true preceding 3-hour history. Global timestamp splits happen later.
    max_rows=max(6000,int(os.getenv("MAX_TRAIN_ROWS","30000")))
    per_city_cap=max(500,max_rows//len(CITIES))
    frames=[]
    source_rows=0
    successful_cities=[]
    for name,coords in CITIES.items():
        try:
            print(f"Fetching {name}: {start} to {end}")
            city_df=build_targets(fetch_city(name,coords,start,end)).dropna(subset=["aqi"]+[f"avg_{key}" for key in FEATURES])
            source_rows += len(city_df)
            if len(city_df)>per_city_cap:
                city_df=city_df.sample(n=per_city_cap,random_state=42)
            frames.append(city_df)
            successful_cities.append(name)
            del city_df
            time.sleep(.3)
        except Exception as exc: print(f"WARNING {name}: {exc}")
    if len(frames)<6: raise SystemExit(f"Only {len(frames)} cities returned training data; at least 6 cities are required.")
    df=pd.concat(frames,ignore_index=True).sort_values(["time","city"]).reset_index(drop=True)
    if len(df)<1000: raise SystemExit(f"Only {len(df)} valid sampled rows; at least 1000 required.")
    print(f"Retained {len(df):,} rows from {source_rows:,} valid source rows across {len(successful_cities)} cities.")
    # Train on the same rolling-average features used by live inference. Split
    # by unique timestamp so different cities from the same hour never leak
    # across train/validation/test partitions.
    X=df[[f"avg_{k}" for k in FEATURES]].copy()
    X.columns=FEATURES
    X=X.replace([np.inf,-np.inf],np.nan); y=df.aqi.clip(0,500)
    unique_times=np.sort(df.time.unique())
    if len(unique_times)<20: raise SystemExit("Not enough distinct 3-hour timestamps for a chronological train/validation/test split.")
    a=max(1,int(len(unique_times)*.70)); b=max(a+1,int(len(unique_times)*.85))
    train_end=unique_times[a]; validation_end=unique_times[min(b,len(unique_times)-1)]
    train_mask=df.time<train_end
    validation_mask=(df.time>=train_end)&(df.time<validation_end)
    test_mask=df.time>=validation_end
    Xtr,ytr=X.loc[train_mask],y.loc[train_mask]
    Xv,yv=X.loc[validation_mask],y.loc[validation_mask]
    Xte,yte=X.loc[test_mask],y.loc[test_mask]
    if min(len(Xtr),len(Xv),len(Xte))<100: raise SystemExit("Chronological split produced too few rows; expand the training date range.")
    models={"random_forest":RandomForestRegressor(n_estimators=120,min_samples_leaf=4,max_leaf_nodes=256,max_features=.9,random_state=42,n_jobs=2),"gradient_boosting":GradientBoostingRegressor(n_estimators=140,learning_rate=.04,max_depth=2,loss="huber",random_state=42),"knn":make_pipeline(StandardScaler(),KNeighborsRegressor(n_neighbors=15,weights="distance",algorithm="kd_tree",n_jobs=2))}
    vp={}
    for k,m in models.items(): m.fit(Xtr,ytr); vp[k]=m.predict(Xv)
    vrmse={k:float(mean_squared_error(yv,p)**.5) for k,p in vp.items()}
    inv={k:1/max(v,1e-6) for k,v in vrmse.items()}; total=sum(inv.values()); weights={k:v/total for k,v in inv.items()}
    tp={k:m.predict(Xte) for k,m in models.items()}; ens=sum(weights[k]*tp[k] for k in models)
    metrics={k:{"r2":float(r2_score(yte,p)),"rmse":float(mean_squared_error(yte,p)**.5),"mae":float(mean_absolute_error(yte,p))} for k,p in {**tp,"weighted_ensemble":ens}.items()}
    # Category accuracy is computed from the actual weighted three-model
    # ensemble output, not from a separate classifier that inference never uses.
    bins=[-1,50,100,200,300,400,500]
    cats=pd.cut(y,bins=bins,labels=False,include_lowest=True).astype(int)
    predicted_categories=pd.cut(np.clip(ens,0,500),bins=bins,labels=False,include_lowest=True).astype(int)
    cat_acc=float(accuracy_score(cats.loc[test_mask],predicted_categories))
    # Refit regression models on train + validation after selecting weights.
    Xfit=pd.concat([Xtr,Xv]); yfit=pd.concat([ytr,yv])
    for m in models.values(): m.fit(Xfit,yfit)
    importances=models["random_forest"].feature_importances_
    model_version="atmoiq-rf-gb-knn-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models":models,"features":FEATURES,"weights":weights,"model_version":model_version},ARTIFACT_PATH)
    artifact={"model_version":model_version,"features":FEATURES,"weights":weights,"validation_rmse":vrmse,"test_metrics":metrics,"category_accuracy":cat_acc,"rows":int(len(df)),"source_rows_before_sampling":int(source_rows),"cities":sorted(df.city.unique().tolist()),"train_period":[str(df.loc[train_mask,"time"].min()),str(df.loc[train_mask,"time"].max())],"validation_period":[str(df.loc[validation_mask,"time"].min()),str(df.loc[validation_mask,"time"].max())],"test_period":[str(df.loc[test_mask,"time"].min()),str(df.loc[test_mask,"time"].max())],"feature_importance":{k:float(v) for k,v in zip(FEATURES,importances)},"target":"Approximate CPCB-breakpoint proxy AQI from native 3-hour Open-Meteo CAMS Global points. PM/NO2/SO2 use 8-point 24-hour means; CO/O3 use a maximum 3-sample approximation to the CPCB 8-hour window. NH3 is unavailable in CAMS Global; no missing features are imputed; not measured CPCB labels","split":"chronological 70/15/15 by timestamp; cities at the same timestamp stay in one split"}
    METRICS_PATH.write_text(json.dumps(artifact,indent=2)); print(json.dumps(artifact,indent=2))
if __name__=="__main__": main()
