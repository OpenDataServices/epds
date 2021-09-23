import 'ol/ol.css';
import Map from 'ol/Map';
import OSM from 'ol/source/OSM';
import GeoJSON from 'ol/format/GeoJSON';
import View from 'ol/View';
import VectorSource from 'ol/source/Vector';
import Overlay from 'ol/Overlay';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer';
import { fromLonLat } from 'ol/proj';
import { bbox as bboxStrategy } from 'ol/loadingstrategy';
import { Circle, Fill, Stroke, Style } from 'ol/style';
import Draw, {
  createBox,
} from 'ol/interaction/Draw';

require('dotenv').config()

/// Raster layer
const osm = new TileLayer({
  source: new OSM(),
  name: 'osm',
});

function getVectorSource(layerName, definedExtent) {
  return new VectorSource({
    format: new GeoJSON(),
    url: function () {
      return (
        `http://${process.env.GEOSERVER_HOST}:8080/geoserver/wfs?` +
        'version=1.1.0&' +
        'request=GetFeature&' +
        'srsname=EPSG:4326&' +
        `typename=EPDS:${layerName}&` +
        'outputFormat=application/json&' +
        `bbox=${definedExtent.join(',')}` +
        ',EPSG:3857'
      );
    },
    strategy: bboxStrategy,
  });
}

/// RSPB Reserves vector layer
function getRSPBReserves(definedExtent) {
  const reserves = new VectorLayer({
    source: getVectorSource('rspb_reserves', definedExtent),
    name: 'reserves',
    style: new Style({
      stroke: new Stroke({
        color: 'rgba(0, 0, 255, 1.0)',
        width: 2,
      }),
      fill: new Fill({color: 'rgba(0, 0, 255, 0.4)',}),
    }),
  });

  return reserves;
}

/// SSSI vector layer
function getSSSI(definedExtent) {
  const sssi = new VectorLayer({
    source: getVectorSource('all_sssi', definedExtent),
    name: 'sssi',
    style: new Style({
      stroke: new Stroke({
        color: 'rgba(0, 255, 0, 1.0)',
        width: 2,
      }),
      fill: new Fill({color: 'rgba(0, 255, 0, 0.4)',}),
    }),
  });

  return sssi;
}



/// TPO vector layer
function getTPO(definedExtent) {
  const tpo = new VectorLayer({
    source: getVectorSource('trees_near_rspb_reserves', definedExtent),
    name: 'tpo',
    style: new Style({
    image: new Circle({
        radius: 4,
        fill: new Fill({color: 'rgba(0, 0, 0, 4)',}),
        stroke: new Stroke({color: 'rgba(255, 0, 0, 1)', 
        width: 2
        })
      })
    }),
  });

  return tpo;
}

/// Solr vector layer
function getSOLR(definedExtent=null) {
  const solr = new VectorLayer({
    source: getVectorSource('Solr_in_SSSI', definedExtent),
    name: "solr",
    style: new Style({
      image: new Circle({
        radius: 4,
        fill: new Fill({color: 'rgba(0, 0, 0, 0.3)',}),
        stroke: new Stroke({color: 'rgba(0, 0, 255, 1)', 
        width: 2
        })
      })
    }),
  });

  return solr;
}


/// Drawing layers
const drawingSource = new VectorSource({wrapX: false});
const drawing = new VectorLayer({
  source: drawingSource,
  name: 'draw',
});

/// Map creation
let MAPMODE = "trees_reserves";
const map = new Map({
  layers: [osm, drawing],
  target: 'map',
  view: new View({
    projection: 'EPSG:3857',
    center: fromLonLat([-3.432, 54.910]),
    zoom: 6,
    minZoom: 6,
  }),
});

function getLayers(definedExtent) {
  if (MAPMODE === "trees_reserves") {
    map.addLayer(getRSPBReserves(definedExtent));
    map.addLayer(getTPO(definedExtent));
  } else if (MAPMODE === "solr_sssi") {
    map.addLayer(getSOLR(definedExtent))
    map.addLayer(getSSSI(definedExtent))
  } else if (MAPMODE === "all_data") {
    map.addLayer(getSSSI(definedExtent))
    map.addLayer(getRSPBReserves(definedExtent));
    map.addLayer(getSOLR(definedExtent))
    map.addLayer(getTPO(definedExtent));
  }
  map.removeLayer(drawing)
}

/// Interactions
function mapmodeSelection() {
  MAPMODE = modeSelect.value;
}

/**
 * Handle change event.
 */
 modeSelect.onchange = function () {
  mapmodeSelection();
};

/// Drawing
let draw; // global so we can remove it later
let drawMode = "none"
function addInteraction() {
  if (drawMode !== 'none') {
    let geometryFunction;
    if (drawMode === 'box') {
      drawMode = 'Circle';
      geometryFunction = createBox();
    }
    draw = new Draw({
      source: drawingSource,
      type: drawMode,
      geometryFunction: geometryFunction,
    });
    draw.on('drawstart', function () {
      drawingSource.clear();
    });
    draw.on('drawend', function (event) {
      const definedExtent = event.feature.getGeometry().getExtent()
      getLayers(definedExtent);
      drawMode = "none";
      map.removeInteraction(draw);
    });
    map.addInteraction(draw);
  }
}

document.getElementById('boxDraw').addEventListener('click', function () {
  map.removeInteraction(draw);
  drawMode = "box";
  addInteraction();
});

document.getElementById ("submitLatLng").addEventListener ("click", function() {
  const input = document.getElementById('latlng').value.trim();
  const splitLatLng = input.split(", ", 2);
  const parsedLatLng = splitLatLng.map(value => parseFloat(value))

  map.getView().animate({zoom: 12, center: fromLonLat([parsedLatLng[1], parsedLatLng[0]])}, function () {
    MAPMODE="all_data"
    const definedExtent = map.getView().calculateExtent(map.getSize())
    getLayers(definedExtent);
  });
});

addInteraction();

popup = document.getElementById('popup');
popupOverlay = new Overlay({
  element: popup,
  offset: [9, 9]
});
map.addOverlay(popupOverlay);

function getFeatureString(layer, feature) {
  if (layer.get('name') === 'reserves') {
    return `RSPB Reserve: ${feature.get('name')}`
  } else if (layer.get('name') === 'tpo') {
    return `Tree protection order: ${feature.get('description')}`
  } else if (layer.get('name') === 'solr') {
    return `Solar farm application: ${feature.get('description')}`
  } else if (layer.get('name') === 'sssi') {
    const countryString = feature.get('country');
    const capitalisedString = countryString.charAt(0).toUpperCase() + countryString.slice(1)
    return `Site of Special Scientific Interest: ${capitalisedString}`
  }
}

map.on('pointermove', (event) => {
  const features = [];
  const popupContent = []
  map.forEachFeatureAtPixel(event.pixel,
      (feature, layer) => {
        if (layer) {
          features.push(feature);
          const values = getFeatureString(layer, feature);
          popupContent.push(values);
          popupContent.push('<br>')
        }
      },
  );
  popup.innerHTML = popupContent.join('');
  popup.hidden = false;
  popupOverlay.setPosition(event.coordinate);
  if (!features || features.length === 0) {
      popup.innerHTML = '';
      popup.hidden = true;
  }
});
