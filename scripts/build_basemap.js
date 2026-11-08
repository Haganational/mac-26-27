// Builds templates/static/basemap.json (keyless vector basemap for travel.html).
// Inputs come from npm packages: world-atlas@2.0.2, us-atlas@3.0.1, topojson-client@3.1.0, @geo-maps/earth-lakes-10km@0.6.0 (extract to ./lakes)
// (npm pack each and extract next to this script), then: node build_basemap.js
const tc = require('./topojson-client-3.1.0/package/dist/topojson-client.min.js');
const fs = require('fs');
const load = f => JSON.parse(fs.readFileSync(f));
const w50 = load('world-atlas-2.0.2/package/countries-50m.json'), w110 = load('world-atlas-2.0.2/package/countries-110m.json');
const us = load('us-atlas-3.0.1/package/states-10m.json');
const r = a => Array.isArray(a[0]) ? a.map(r) : [Math.round(a[0]*100)/100, Math.round(a[1]*100)/100];
const DETAIL = ['United States of America','Mexico','Bahamas','Cuba','Puerto Rico','Jamaica','Haiti','Dominican Rep.','Belize','Guatemala','Honduras','El Salvador','Nicaragua','Costa Rica','Panama','Cayman Is.','Turks and Caicos Is.','Bermuda'];
const feat = (w, names) => tc.feature(w, w.objects.countries).features.filter(f => f.geometry && names(f.properties.name))
  .map(f => ({ type:'Feature', properties:{ name:f.properties.name }, geometry:{ type:f.geometry.type, coordinates:r(f.geometry.coordinates) } }));
const countries = [...feat(w50, n => DETAIL.includes(n)), ...feat(w110, n => n === 'Canada')];
const borders = tc.mesh(w50, w50.objects.countries, (a,b)=>a!==b && [a,b].every(x=>DETAIL.includes(x.properties.name)||x.properties.name==='Canada'));
const states = tc.mesh(us, us.objects.states, (a,b)=>a!==b);
const out = { countries:{type:'FeatureCollection',features:countries}, borders:{type:'Feature',geometry:{type:borders.type,coordinates:r(borders.coordinates)}}, states:{type:'Feature',geometry:{type:states.type,coordinates:r(states.coordinates)}} };
fs.writeFileSync('basemap.json', JSON.stringify(out));
console.log(fs.statSync('basemap.json').size, require('zlib').gzipSync(fs.readFileSync('basemap.json')).length);
// Lakes (OSM via @geo-maps/earth-lakes-10km, ODbL): keep larger lakes inside North America's bounding box.
const lk = load('lakes/package/map.geo.json').geometries[0].coordinates.filter(poly => {
  const ring = poly[0]; let minx=1e9,maxx=-1e9,miny=1e9,maxy=-1e9;
  for (const [x,y] of ring) { minx=Math.min(minx,x); maxx=Math.max(maxx,x); miny=Math.min(miny,y); maxy=Math.max(maxy,y); }
  return minx > -130 && maxx < -60 && miny > 14 && maxy < 52 && (maxx-minx)*(maxy-miny) > 0.05;
});
out.lakes = { type:'Feature', geometry:{ type:'MultiPolygon', coordinates:r(lk) } };
fs.writeFileSync('basemap.json', JSON.stringify(out));
console.log('with lakes', lk.length, fs.statSync('basemap.json').size, require('zlib').gzipSync(fs.readFileSync('basemap.json')).length);
