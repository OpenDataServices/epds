import 'ol/ol.css';
import Map from 'ol/Map';
import OSM from 'ol/source/OSM';
import GeoJSON from 'ol/format/GeoJSON';
import View from 'ol/View';
import VectorSource from 'ol/source/Vector';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer';
import { fromLonLat } from 'ol/proj';
import { bbox as bboxStrategy } from 'ol/loadingstrategy';
import { Circle, Fill, Stroke, Style } from 'ol/style';
import Draw, {
  createBox,
} from 'ol/interaction/Draw';


/// Raster layer
const osm = new TileLayer({
  source: new OSM(),
});

/// RSPB Reserves vector layer
const reservesVectorSource = new VectorSource({
  format: new GeoJSON(),
  url: function (extent) {
    return (
      'http://65.21.225.158:8080/geoserver/wfs?' +
      'version=1.1.0&' +
      'request=GetFeature&' +
      'srsname=EPSG:4326&' +
      'typename=EPDS:rspb_reserves&' +
      'outputFormat=application/json&' +
      'bbox=' +
        extent.join(',') +
      ',EPSG:3857'
    );
  },
  strategy: bboxStrategy,
});

const reserves = new VectorLayer({
  source: reservesVectorSource,
  style: new Style({
    stroke: new Stroke({
      color: 'rgba(0, 0, 255, 1.0)',
      width: 2,
    }),
    fill: new Fill({color: 'rgba(0, 0, 255, 0.4)',}),
  }),
});

/// SSSI vector layer
const sssiVectorSource = new VectorSource({
  format: new GeoJSON(),
  url: function (extent) {
    return (
      'http://65.21.225.158:8080/geoserver/wfs?' +
      'version=1.1.0&' +
      'request=GetFeature&' +
      'srsname=EPSG:4326&' +
      'typename=EPDS:all_sssi&' +
      'outputFormat=application/json&' +
      'bbox=' +
        extent.join(',') +
      ',EPSG:3857'
    );
  },
  strategy: bboxStrategy,
});

const sssi = new VectorLayer({
  source: sssiVectorSource,
  style: new Style({
    stroke: new Stroke({
      color: 'rgba(0, 255, 0, 1.0)',
      width: 2,
    }),
    fill: new Fill({color: 'rgba(0, 255, 0, 0.4)',}),
  }),
});

/// TPO vector layer
const treesVectorSource = new VectorSource({
  format: new GeoJSON(),
  url: function (extent) {
    return (
      'http://65.21.225.158:8080/geoserver/wfs?' +
      'version=1.1.0&' +
      'request=GetFeature&' +
      'srsname=EPSG:4326&' +
      'typename=EPDS:trees_near_rspb_reserves&' +
      'outputFormat=application/json&' +
      'bbox=' +
        extent.join(',') +
      ',EPSG:3857'
    );
  },
  strategy: bboxStrategy,
});

const trees = new VectorLayer({
  source: treesVectorSource,
  style: new Style({
    image: new Circle({
      radius: 4,
      fill: new Fill({color: 'rgba(0, 0, 0, 0.1)',}),
      stroke: new Stroke({color: 'rgba(255, 0, 0, 0.6)', 
      width: 2
      })
    })
  }),
});

/// Solr vector layer
const solrVectorSource = new VectorSource({
  format: new GeoJSON(),
  url: function (extent) {
    return (
      'http://65.21.225.158:8080/geoserver/wfs?' +
      'version=1.1.0&' +
      'request=GetFeature&' +
      'srsname=EPSG:4326&' +
      'typename=EPDS:Solr_in_SSSI&' +
      'outputFormat=application/json&' +
      'bbox=' +
        extent.join(',') +
      ',EPSG:3857'
    );
  },
  strategy: bboxStrategy,
});

const solr = new VectorLayer({
  source: solrVectorSource,
  style: new Style({
    image: new Circle({
      radius: 4,
      fill: new Fill({color: 'rgba(0, 0, 0, 0.1)',}),
      stroke: new Stroke({color: 'rgba(0, 0, 255, 0.6)', 
      width: 2
      })
    })
  }),
});

/// Drawing layers
const drawingSource = new VectorSource({wrapX: false});
const drawing = new VectorLayer({
  source: drawingSource,
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
  }),
});

function getLayers() {
  if (MAPMODE === "trees_reserves") {
    map.removeLayer(solr)
    map.removeLayer(sssi)
    map.addLayer(reserves);
    map.addLayer(trees);
  } else if (MAPMODE === "solr_sssi") {
    map.removeLayer(reserves);
    map.removeLayer(trees);
    map.addLayer(solr)
    map.addLayer(sssi)
  }
}

/// Interactions
function mapmodeSelection() {
  MAPMODE = modeSelect.value;
  getLayers()
}

/**
 * Handle change event.
 */
 modeSelect.onchange = function () {
  mapmodeSelection();
};

mapmodeSelection();


/// Drawing
let draw; // global so we can remove it later
let drawMode = "none"
function addInteraction() {
  console.log(drawMode)
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
    draw.on('drawend', function () {
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

addInteraction();
