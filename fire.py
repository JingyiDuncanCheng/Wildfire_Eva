# fire_building_viz.py 北美单位版 🗽
# 功能：交互式火点与建筑数据地图（英尺/平方英尺单位）

FIRE_CSV = r"fire_total.csv"
BLDG_JSON = r"2023_Buildings_with_DINS_data.geojson"
FUEL_TIF = r"燃料数据.tif"
OUT_HTML = "fire_building_map.html"

import pandas as pd
import geopandas as gpd
import numpy as np
import folium
import rasterio
import json
import re
from rasterstats import zonal_stats
from folium.plugins import MeasureControl
from branca.element import MacroElement, Template
from shapely.geometry import Point

# ------------------ 单位转换常数 ------------------
M_TO_FT = 3.28084  # 米转英尺


# ------------------ 辅助函数 ------------------
def convert_numpy_types(val):
    """转换numpy类型到Python原生类型"""
    if isinstance(val, (np.integer)):
        return int(val)
    if isinstance(val, (np.floating)):
        return float(val)
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    return val


def clean_coordinate(coord, coord_type):
    """
    清洗并验证地理坐标数据
    :param coord: 原始坐标值（支持字符串/数值）
    :param coord_type: 坐标类型，'latitude'（纬度）或 'longitude'（经度）
    :return: 标准化的浮点数值或np.nan（无效时）
    """
    try:
        # 转换输入为字符串处理
        str_coord = str(coord).strip().replace(",", ".")

        # 提取第一个有效数值（支持正负号、小数）
        match = re.search(r"^[-+]?\d*\.?\d+", str_coord)
        if not match:
            return np.nan

        val = float(match.group())

        # 根据坐标类型验证范围
        if coord_type == 'latitude':
            if not (-90 <= val <= 90):
                return np.nan
        elif coord_type == 'longitude':
            if not (-180 <= val <= 180):
                return np.nan
        else:
            raise ValueError(f"无效坐标类型: {coord_type}")

        return round(val, 6)  # 保留6位小数精度

    except (TypeError, ValueError, AttributeError):
        return np.nan


# ------------------ 数据预处理 ------------------
# 1. 火点数据处理（增强清洗）
try:
    fire_df = pd.read_csv(FIRE_CSV, parse_dates=["datetime"])

    # 验证必要字段
    required_cols = ["latitude", "longitude", "datetime", "track", "scan"]
    missing_cols = [col for col in required_cols if col not in fire_df.columns]
    if missing_cols:
        raise ValueError(f"火点数据缺少必要字段: {', '.join(missing_cols)}")

    # 数据清洗
    fire_df = fire_df.assign(
        latitude=fire_df["latitude"].apply(
            lambda x: clean_coordinate(x, 'latitude')
        ),
        longitude=fire_df["longitude"].apply(
            lambda x: clean_coordinate(x, 'longitude')
        )
    ).dropna(subset=["latitude", "longitude"])

except Exception as e:
    print(f"火点数据加载失败: {str(e)}")
    exit()

# 2. 建筑数据处理（单位转换与安全检查）
bldg_gdf = gpd.read_file(BLDG_JSON).to_crs("EPSG:4326")
bldg_gdf = bldg_gdf.assign(
    height_ft=(bldg_gdf["HEIGHT"].fillna(0) * M_TO_FT).clip(lower=0),
    area_sqft=(bldg_gdf["AREA"].fillna(0) * (M_TO_FT ** 2)).clip(lower=0)
).query("height_ft >= 0 and area_sqft >= 0")

# 3. 燃料数据处理（安全计算）
with rasterio.open(FUEL_TIF) as src:
    zs = zonal_stats(
        bldg_gdf.geometry,
        src.read(1),
        affine=src.transform,
        stats=["mean"],
        nodata=src.nodata
    )
fuel_mean = np.array([z["mean"] or 0 for z in zs])

# 安全归一化计算
height_max = bldg_gdf["height_ft"].max() or 1
area_max = bldg_gdf["area_sqft"].max() or 1
fuel_normalized = fuel_mean / fuel_mean.max() if fuel_mean.max() > 0 else np.zeros_like(fuel_mean)

bldg_gdf["vulnerability"] = (
        0.5 * (bldg_gdf["height_ft"] / height_max) +
        0.3 * (bldg_gdf["area_sqft"] / area_max) +
        0.2 * fuel_normalized
).clip(0, 1)

# ------------------ 地图初始化 ------------------
if fire_df.empty:
    raise ValueError("清洗后无有效火点数据")

center = [fire_df["latitude"].mean(), fire_df["longitude"].mean()]
m = folium.Map(
    location=center,
    zoom_start=10,
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri World Imagery',
    control_scale=True
)


# ------------------ 建筑图层 ------------------
def get_color(feature):
    h = feature['properties']['height_ft']
    return (
        '#FFEDA0' if h < 32.8 else
        '#FEDD70' if h < 65.6 else
        '#FEB24C' if h < 98.4 else
        '#FDBD3C' if h < 164 else
        '#FC4E2A' if h < 328 else
        '#E31A1C'
    )


def style_function(feature):
    try:
        vul = float(feature['properties'].get('vulnerability', 0.0))
        opacity = max(0.0, min(1.0, 0.6 * vul + 0.2))
    except:
        vul = 0.0
        opacity = 0.2

    return {
        'fillColor': get_color(feature),
        'color': '#444',
        'weight': 0.5,
        'fillOpacity': opacity
    }


folium.GeoJson(
    bldg_gdf,
    name='🏢 建筑',
    style_function=style_function,
    popup=folium.GeoJsonPopup(
        fields=['height_ft', 'area_sqft', 'vulnerability'],
        aliases=['高度（英尺）', '面积（平方英尺）', '脆弱性指数'],
        localize=True
    ),
    tooltip=folium.GeoJsonTooltip(
        fields=["height_ft"],
        aliases=["建筑高度："]
    )
).add_to(m)

# ------------------ 火点图层（含2km缓冲区）------------------
fires_fg = folium.FeatureGroup(name='🔥 火点', show=True)

for idx, row in fire_df.iterrows():
    # 信息弹窗
    popup_html = f"""
    <div style="min-width:250px;">
        <h4 style="color:#d9534f; margin:0 0 8px;">火点详情</h4>
        <div><b>时间：</b>{row['datetime'].strftime('%Y-%m-%d %H:%M')}</div>
        <div><b>坐标：</b>{row['latitude']:.4f}°N, {row['longitude']:.4f}°E</div>
        <div><b>轨道：</b>{row['track']}</div>
        <div><b>扫描：</b>{row['scan']}</div>
    </div>
    """

    # 2公里缓冲区
    folium.Circle(
        location=[row['latitude'], row['longitude']],
        radius=2000,
        color='#ff4500',
        fill_color='#ff6347',
        fill_opacity=0.2,
        weight=1,
        popup=folium.Popup(popup_html, max_width=300),
        smooth_factor=0.5
    ).add_to(fires_fg)

    # 中心点标记
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=4,
        color='#ff0000',
        fill=True,
        fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(fires_fg)

# ------------------ 交互组件 ------------------
dates = sorted(fire_df['datetime'].dt.strftime('%Y-%m-%d').unique())
macro = MacroElement()
macro._template = Template(f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .leaflet-control-datefilter {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
        }}
        .legend {{
            background: white;
            padding: 10px;
            line-height: 1.5;
        }}
        .legend-icon {{
            width: 20px;
            height: 20px;
            display: inline-block;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <script>
        var fireLayer = L.featureGroup();
        var dateSelect = null;

        map.whenReady(function() {{
            // 日期选择器
            var dateControl = L.control({{position: 'topright'}});
            dateControl.onAdd = function() {{
                var div = L.DomUtil.create('div', 'leaflet-control-datefilter');
                div.innerHTML = `
                    <b>日期筛选：</b>
                    <select id="dateSelect" style="width:150px;">
                        <option value="all">全部日期</option>
                        {"".join([f'<option value="{d}">{d}</option>' for d in dates])}
                    </select>
                `;
                return div;
            }};
            dateControl.addTo(map);

            // 图例
            var legend = L.control({{position: 'bottomright'}});
            legend.onAdd = function() {{
                var div = L.DomUtil.create('div', 'legend');
                div.innerHTML = `
                    <h4>图例说明</h4>
                    <div><div class="legend-icon" style="background:#ff4500;opacity:0.2;"></div>2公里缓冲区</div>
                    <div><div class="legend-icon" style="background:#ff0000;"></div>火点中心</div>
                    <div><div class="legend-icon" style="background:#E31A1C;"></div>高层建筑 >328ft</div>
                `;
                return div;
            }};
            legend.addTo(map);

            // 日期筛选功能
            document.getElementById('dateSelect').addEventListener('change', function() {{
                var selectedDate = this.value;
                fireLayer.eachLayer(function(layer) {{
                    if(selectedDate === 'all' || layer.date === selectedDate) {{
                        map.addLayer(layer);
                    }} else {{
                        map.removeLayer(layer);
                    }}
                }});
            }});
        }});
    </script>
</body>
</html>
""")

m.get_root().add_child(macro)
m.add_child(MeasureControl(position='topleft', primary_length_unit='miles'))
fires_fg.add_to(m)
folium.LayerControl().add_to(m)

# ------------------ 数据质量报告 ------------------
print("=== 数据质量报告 ===")
print(f"建筑数量：{len(bldg_gdf)}")
print(f"建筑高度范围：{bldg_gdf.height_ft.min():.1f} - {bldg_gdf.height_ft.max():.1f} ft")
print(f"火点时间范围：{fire_df.datetime.min().strftime('%Y-%m-%d')} 至 {fire_df.datetime.max().strftime('%Y-%m-%d')}")
print(f"轨道标识范围：{fire_df.track.min()} - {fire_df.track.max()}")
print("扫描类型分布：")
print(fire_df.scan.value_counts().to_string())

# === ADD just above the existing m.save(...) line =========================
def get_fire_layers_geojson():
    """
    Return two ready‑to‑serve blobs:
      • GeoJSON for the buildings layer
      • Plain‑dict list for the fire points
    Nothing heavy is recomputed here – it reuses the
    already‑loaded bldg_gdf / fire_df that fire.py prepared on import.
    """
    # GeoPandas → GeoJSON string → dict (so Flask can jsonify it)
    buildings_geojson = json.loads(
        bldg_gdf.to_crs(epsg=4326).to_json()
    )
    fires_list = (
        fire_df[["latitude", "longitude", "datetime", "track", "scan"]]
        .applymap(convert_numpy_types)
        .to_dict("records")
    )
    return {"buildings": buildings_geojson, "fires": fires_list}
# === END PATCH ============================================================

# ------------------ 保存地图 ------------------
m.save(OUT_HTML)
print(f"\n✅ 地图已生成：{OUT_HTML}")