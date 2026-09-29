/* ============================================================
   Houston Inequality Map — app.js
   Layered map of spatial inequality in Houston.
   Every layer shown here comes from a named public source; see About.
   ============================================================ */

(function () {
  'use strict';

  // ── Constants ──────────────────────────────────────────────
  var HOLC_YEAR = 1937;          // Big Ten Academic Alliance catalog date for the Houston sheet
  var ACS_LABEL = 'ACS 2018–22'; // Census ACS 5-year estimates
  var DECADE_MIN = 1930;
  var DECADE_MAX = 2020;
  var LOAD_TRI = false;
  var LOAD_LENDING = true;  // data/capital/hmda_tracts.geojson, built by scripts/capital/build_hmda_tracts.py

  // ── State ──────────────────────────────────────────────────
  var state = {
    currentDecade: DECADE_MAX,
    activeLayers: new Set(),
    layerData: {},
    layerGroups: {},
    map: null,
    timelineEvents: [],
    narrative: { decade: null, index: 0, dismissed: new Set() },
    politicalType: 'congressional',
    capitalIndicator: 'value_change_10y',
    lendingIndicator: 'investor_share',
  };

  // ── Colors ─────────────────────────────────────────────────
  var incomeScale = chroma.scale('viridis').domain([20000, 250000]);
  var NO_DATA = '#3a3f47';

  var partyColors = { D: '#3b82f6', R: '#ef4444', NP: '#a78bfa', Unknown: '#6b7280' };
  var partyNames = { D: 'Democrat', R: 'Republican', NP: 'Nonpartisan office', Unknown: 'Unknown' };

  var raceColors = {
    white: '#1b9e77',
    black: '#d95f02',
    hispanic: '#7570b3',
    asian: '#e7298a',
    diverse: '#9ca3af',
  };

  var holcColors = { A: '#4daf4a', B: '#377eb8', C: '#ffff33', D: '#e41a1c' };
  var HOLC_UNGRADED = '#8b8b8b';
  // HOLC's own category names
  var holcLabels = { A: 'Best', B: 'Still Desirable', C: 'Definitely Declining', D: 'Hazardous' };

  // ── Helpers ────────────────────────────────────────────────
  function pct(v) { return v != null ? v.toFixed(1) + '%' : '—'; }
  function money(v) { return v != null ? '$' + Math.round(v).toLocaleString() : 'No data'; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function link(url, text) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text || 'source') + '</a>';
  }

  // Feature clicks must not reach the map's own click handler (which closes the panel).
  function onClick(layer, fn) {
    layer.on('click', function (e) {
      L.DomEvent.stopPropagation(e);
      fn(e);
    });
  }

  // A point guaranteed to sit inside a polygon: midpoint of the widest horizontal
  // run through the bounding-box centre (bounds centres can fall outside U-shapes).
  function interiorPoint(layer) {
    var b = layer.getBounds();
    var c = b.getCenter();
    var rings = [];
    (function collect(ll) {
      if (!ll.length) return;
      if (ll[0] instanceof L.LatLng) { rings.push(ll); return; }
      ll.forEach(collect);
    })(layer.getLatLngs());
    var y = c.lat, xs = [];
    rings.forEach(function (ring) {
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var a = ring[i], p = ring[j];
        if ((a.lat > y) !== (p.lat > y)) {
          xs.push(a.lng + (y - a.lat) * (p.lng - a.lng) / (p.lat - a.lat));
        }
      }
    });
    xs.sort(function (m, n) { return m - n; });
    var best = null, w = -1;
    for (var k = 0; k + 1 < xs.length; k += 2) {
      if (xs[k + 1] - xs[k] > w) { w = xs[k + 1] - xs[k]; best = (xs[k] + xs[k + 1]) / 2; }
    }
    return best == null ? c : L.latLng(y, best);
  }

  // ── Map ────────────────────────────────────────────────────
  function initMap() {
    state.map = L.map('map', { center: [29.76, -95.37], zoom: 11 });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(state.map);
    state.map.attributionControl.addAttribution(
      'Redlining: <a href="https://dsl.richmond.edu/panorama/redlining/" target="_blank" rel="noopener">Mapping Inequality</a> (Nelson, Winling et al., CC BY-NC-SA)'
    );
    ['redlining', 'highways', 'income', 'race', 'floods', 'pollution', 'capital', 'lending', 'political'].forEach(function (n) {
      state.layerGroups[n] = L.layerGroup();
    });
  }

  // ── Data ───────────────────────────────────────────────────
  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
      return r.json();
    });
  }

  function loadAllData() {
    var files = {
      redlining: 'data/redlining/houston_holc.geojson',
      highways: 'data/infrastructure/highways.geojson',
      income: 'data/census/income_2020.geojson',
      race: 'data/census/race_2020.geojson',
      floods: 'data/environment/flood_zones.geojson',
      capital: 'data/capital/capital_flow.geojson',
      political: 'data/political/districts.geojson',
    };
    // Optional layer: set to true after scripts/fetch_tri.py has written real EPA TRI data.
    if (LOAD_TRI) files.pollution = 'data/environment/tri_sites.geojson';
    if (LOAD_LENDING) files.lending = 'data/capital/hmda_tracts.geojson';
    var loads = Object.keys(files).map(function (k) {
      return getJSON(files[k]).then(function (d) { state.layerData[k] = d; });
    });
    loads.push(getJSON('data/annotations/timeline_events.json').then(function (d) { state.timelineEvents = d; }));
    return Promise.allSettled(loads).then(function (results) {
      results.forEach(function (r) { if (r.status === 'rejected') console.info('Layer not loaded:', r.reason.message); });
      // Hide layer toggles that have no data
      Object.keys(builders).forEach(function (k) {
        var d = state.layerData[k];
        var group = document.getElementById('group-' + k);
        if (group && !(d && d.features && d.features.length)) group.classList.add('hidden-layer-group');
      });
    });
  }

  // ── Layers ─────────────────────────────────────────────────
  function buildRedliningLayer() {
    var group = state.layerGroups.redlining;
    group.clearLayers();
    var data = state.layerData.redlining;
    if (!data) return;
    L.geoJSON(data, {
      style: function (f) {
        var c = holcColors[f.properties.grade] || HOLC_UNGRADED;
        return { fillColor: c, fillOpacity: 0.35, color: c, weight: 1.5, opacity: 0.8 };
      },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'redlining'); });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.55, weight: 2.5 }); });
        layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.35, weight: 1.5 }); });
      },
    }).addTo(group);
  }

  function highwayStatus(p, decade) {
    var opened = p.open_year ? Math.floor(p.open_year / 10) * 10 : null;
    var done = p.completion_year ? Math.floor(p.completion_year / 10) * 10 : opened;
    if (opened == null || decade < opened) return 'hidden';
    return decade < done ? 'building' : 'open';
  }

  function buildHighwayLayer() {
    var group = state.layerGroups.highways;
    group.clearLayers();
    var data = state.layerData.highways;
    if (!data) return;
    var decade = state.currentDecade;

    data.features.forEach(function (feature) {
      var p = feature.properties;
      var status = highwayStatus(p, decade);
      if (status === 'hidden') return;

      L.geoJSON(feature, {
        style: { color: '#ff8c00', weight: 3, opacity: status === 'open' ? 0.9 : 0.6, dashArray: status === 'building' ? '8 6' : null },
        onEachFeature: function (feat, layer) { onClick(layer, function () { showInfoPanel(feat, 'highways'); }); },
      }).addTo(group);

      var at = p.label_at;
      if (!at) {
        var line = feature.geometry.type === 'MultiLineString'
          ? feature.geometry.coordinates.reduce(function (a, b) { return b.length > a.length ? b : a; })
          : feature.geometry.coordinates;
        at = line[Math.floor(line.length / 2)];
      }
      if (at) {
        L.marker([at[1], at[0]], {
          icon: L.divIcon({ className: 'highway-label', html: '<span>' + esc(p.designation) + '</span>', iconSize: null }),
          interactive: false,
        }).addTo(group);
      }
    });
  }

  function buildIncomeLayer() {
    var group = state.layerGroups.income;
    group.clearLayers();
    var data = state.layerData.income;
    if (!data) return;
    L.geoJSON(data, {
      style: function (f) {
        var v = f.properties.income_2020;
        return { fillColor: v != null ? incomeScale(v).hex() : NO_DATA, fillOpacity: 0.6, color: 'rgba(255,255,255,0.15)', weight: 1 };
      },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'income'); });
        layer.bindTooltip(function () {
          return '<strong>' + esc(f.properties.name) + '</strong><br>Median income: ' + money(f.properties.income_2020);
        }, { sticky: true, className: 'dark-tooltip' });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.8, weight: 2, color: 'rgba(255,255,255,0.4)' }); });
        layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.6, weight: 1, color: 'rgba(255,255,255,0.15)' }); });
      },
    }).addTo(group);
  }

  function dominantGroup(p) {
    var vals = { white: p.pct_white_2020, black: p.pct_black_2020, hispanic: p.pct_hispanic_2020, asian: p.pct_asian_2020 };
    if (vals.white == null) return null;
    var best = null, max = -1, tie = false;
    Object.keys(vals).forEach(function (k) {
      var v = vals[k] || 0;
      if (v > max) { max = v; best = k; tie = false; } else if (v === max) { tie = true; }
    });
    return max > 50 && !tie ? best : 'diverse';
  }

  function buildRaceLayer() {
    var group = state.layerGroups.race;
    group.clearLayers();
    var data = state.layerData.race;
    if (!data) return;
    L.geoJSON(data, {
      style: function (f) {
        var d = dominantGroup(f.properties);
        return { fillColor: d ? raceColors[d] : NO_DATA, fillOpacity: 0.5, color: 'rgba(255,255,255,0.1)', weight: 1 };
      },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'race'); });
        layer.bindTooltip(function () {
          var p = f.properties;
          return '<strong>' + esc(p.name) + '</strong><br>' +
            'White ' + pct(p.pct_white_2020) + ' · Black ' + pct(p.pct_black_2020) +
            ' · Hispanic ' + pct(p.pct_hispanic_2020) + ' · Asian ' + pct(p.pct_asian_2020);
        }, { sticky: true, className: 'dark-tooltip' });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.75, weight: 2, color: 'rgba(255,255,255,0.3)' }); });
        layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.5, weight: 1, color: 'rgba(255,255,255,0.1)' }); });
      },
    }).addTo(group);
  }

  function floodStyle(p) {
    var moderate = p.flood_risk === 'moderate';
    return {
      fillColor: p.flood_risk === 'coastal' ? '#0066cc' : '#0064ff',
      fillOpacity: moderate ? 0.12 : 0.35,
      color: '#0088ff',
      weight: moderate ? 0.5 : 1,
      opacity: 0.5,
    };
  }

  function buildFloodLayer() {
    var group = state.layerGroups.floods;
    group.clearLayers();
    var data = state.layerData.floods;
    if (!data) return;
    L.geoJSON(data, {
      style: function (f) { return floodStyle(f.properties); },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'floods'); });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.55, weight: 2 }); });
        layer.on('mouseout', function () { layer.setStyle(floodStyle(f.properties)); });
      },
    }).addTo(group);
  }

  // Real EPA TRI facilities (name + location only). The layer stays hidden until
  // scripts/fetch_tri.py has produced data/environment/tri_sites.geojson.
  function buildPollutionLayer() {
    var group = state.layerGroups.pollution;
    group.clearLayers();
    var data = state.layerData.pollution;
    if (!data) return;
    data.features.forEach(function (f) {
      var c = f.geometry.coordinates;
      var m = L.circleMarker([c[1], c[0]], { radius: 5, fillColor: '#ff8c00', fillOpacity: 0.8, color: '#ffb366', weight: 1 });
      onClick(m, function () { showInfoPanel(f, 'pollution'); });
      m.bindTooltip(esc(f.properties.facility_name || 'TRI facility'), { className: 'dark-tooltip' });
      m.addTo(group);
    });
  }

  function buildPoliticalLayer() {
    var group = state.layerGroups.political;
    group.clearLayers();
    var data = state.layerData.political;
    if (!data) return;
    var filtered = { type: 'FeatureCollection', features: data.features.filter(function (f) {
      return f.properties.district_type === state.politicalType;
    }) };
    L.geoJSON(filtered, {
      style: function (f) {
        var c = partyColors[f.properties.party] || partyColors.Unknown;
        return { fillColor: c, fillOpacity: 0.08, color: c, weight: 3, opacity: 0.9, dashArray: '6 4' };
      },
      onEachFeature: function (f, layer) {
        var p = f.properties;
        var c = partyColors[p.party] || partyColors.Unknown;
        L.marker(interiorPoint(layer), {
          icon: L.divIcon({
            className: 'political-label',
            html: '<span style="color:' + c + ';border-color:' + c + '">' + esc(p.district_number || p.district_id) + '</span>',
            iconSize: null,
          }),
          interactive: false,
        }).addTo(group);
        onClick(layer, function () { showInfoPanel(f, 'political'); });
        layer.bindTooltip('<strong>' + esc(p.name) + '</strong><br><span style="color:' + c + '">' +
          esc(p.representative) + (p.party === 'D' || p.party === 'R' ? ' (' + p.party + ')' : '') + '</span>',
          { sticky: true, className: 'dark-tooltip' });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.25, weight: 4, dashArray: null }); });
        layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.08, weight: 3, dashArray: '6 4' }); });
      },
    }).addTo(group);
  }

  var builders = {
    redlining: buildRedliningLayer,
    highways: buildHighwayLayer,
    income: buildIncomeLayer,
    race: buildRaceLayer,
    floods: buildFloodLayer,
    pollution: buildPollutionLayer,
    capital: buildCapitalLayer,
    lending: buildLendingLayer,
    political: buildPoliticalLayer,
  };


  // ── Capital Flow (Zillow + Census ACS, by ZIP) ─────────────
  // Descriptive market indicators only; no composite "risk" score.
  function signed(v, unit) { return v == null ? 'No data' : (v > 0 ? '+' : '') + v.toFixed(1) + unit; }
  var DIVERGING = ['#2166ac', '#f7f7f7', '#b2182b'];
  var CAPITAL_INDICATORS = {
    value_change_10y: { label: 'Home value change, 10 years', short: '10-yr value change',
      scale: chroma.scale(['#fff5eb', '#fd8d3c', '#7f2704']).domain([0, 50, 100]), min: '0% or less', max: '+100%',
      fmt: function (v) { return signed(v, '%'); },
      desc: 'Change in Zillow’s typical home value (ZHVI), {d10} to {latest}. Not adjusted for inflation.' },
    value_change_1y: { label: 'Home value change, 1 year', short: '1-yr value change',
      scale: chroma.scale(DIVERGING).domain([-10, 0, 10]), min: '−10%', max: '+10%',
      fmt: function (v) { return signed(v, '%'); },
      desc: 'Change in Zillow’s typical home value (ZHVI), {d1} to {latest}. Blue = falling, red = rising.' },
    rent_change_3y: { label: 'Rent change, 3 years', short: '3-yr rent change',
      scale: chroma.scale(DIVERGING).domain([-10, 0, 10]), min: '−10%', max: '+10%',
      fmt: function (v) { return signed(v, '%'); },
      desc: 'Change in Zillow’s observed asking rent (ZORI), {d3} to {latest}. Grey where Zillow has too few listings.' },
    rent_change_1y: { label: 'Rent change, 1 year', short: '1-yr rent change',
      scale: chroma.scale(DIVERGING).domain([-8, 0, 8]), min: '−8%', max: '+8%',
      fmt: function (v) { return signed(v, '%'); },
      desc: 'Change in Zillow’s observed asking rent (ZORI), {d1} to {latest}.' },
    home_value: { label: 'Typical home value', short: 'Home value',
      scale: chroma.scale('viridis').domain([100000, 1000000]), min: '$100K', max: '$1M+',
      fmt: function (v) { return money(v); },
      desc: 'Zillow Home Value Index (mid-tier homes), {latest}.' },
    rent: { label: 'Typical asking rent', short: 'Asking rent',
      scale: chroma.scale('viridis').domain([900, 2500]), min: '$900', max: '$2,500+',
      fmt: function (v) { return v == null ? 'No data' : money(v) + '/mo'; },
      desc: 'Zillow Observed Rent Index, {latest}: typical asking rent on new leases, which runs above what existing tenants pay.' },
    price_to_income: { label: 'Home value to income', short: 'Value ÷ income',
      scale: chroma.scale(['#ffffcc', '#fd8d3c', '#800026']).domain([2, 5, 8]), min: '2×', max: '8×+',
      fmt: function (v) { return v == null ? 'No data' : v.toFixed(1) + '×'; },
      desc: 'Typical home value ({latest}) divided by median household income ({acs}). Higher = less affordable to local earners.' },
    rent_burdened_pct: { label: 'Rent-burdened renters', short: 'Rent-burdened',
      scale: chroma.scale(['#ffffcc', '#fd8d3c', '#800026']).domain([25, 50, 75]), min: '25%', max: '75%+',
      fmt: function (v) { return pct(v); },
      desc: 'Share of renter households paying 30% or more of income on rent ({acs}).' },
    renter_pct: { label: 'Renter share', short: 'Renters',
      scale: chroma.scale(['#f7fbff', '#6baed6', '#08306b']).domain([0, 50, 100]), min: '0%', max: '100%',
      fmt: function (v) { return pct(v); },
      desc: 'Share of occupied homes that are rented ({acs}).' },
    company_owned_pct: { label: 'Homes owned by companies', short: 'Company-owned',
      scale: chroma.scale(['#f2f0f7', '#9e9ac8', '#3f007d']).domain([0, 6, 12]), min: '0%', max: '12%+',
      fmt: function (v) { return pct(v); },
      desc: 'Share of single-family homes whose owner is an LLC, corporation, partnership or large rental operator (appraisal-district records, {own}). Builders, banks, governments and family trusts are excluded, and so are company-held homes built in the last two years, which are mostly developers’ unsold inventory. Countywide: about 5%.' },
    recent_company_pct: { label: 'Recent buyers that are companies', short: 'Recent buyers: companies',
      scale: chroma.scale(['#f2f0f7', '#9e9ac8', '#3f007d']).domain([0, 15, 30]), min: '0%', max: '30%+',
      fmt: function (v) { return pct(v); },
      desc: 'Of existing single-family homes (built before the last two years) that changed owners since {since}, the share now owned by a company or rental operator (appraisal-district records).' },
    institutional_pct: { label: 'Homes owned by large rental operators', short: 'Large rental operators',
      scale: chroma.scale(['#f2f0f7', '#9e9ac8', '#3f007d']).domain([0, 2, 4]), min: '0%', max: '4%+',
      fmt: function (v) { return pct(v); },
      desc: 'Share of single-family homes owned by the big national single-family landlords (Invitation Homes, American Homes 4 Rent, Progress Residential, FirstKey, Tricon and others), matched by holding-company name or the operator’s own office address. Homes these firms manage for other owners are not counted. List in scripts/capital/owner_classes.py.' },
    out_of_state_owner_pct: { label: 'Owners mailing from outside Texas', short: 'Out-of-state owners',
      scale: chroma.scale(['#f2f0f7', '#9e9ac8', '#3f007d']).domain([0, 3, 6]), min: '0%', max: '6%+',
      fmt: function (v) { return pct(v); },
      desc: 'Share of single-family homes whose owner’s tax-mailing address is outside Texas (appraisal-district records, {own}).' },
  };

  function capitalMeta() {
    var m = (state.layerData.capital && state.layerData.capital.metadata) || {};
    var latest = m.latest_month || '';
    function mo(d) {
      if (!d) return '';
      var names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return names[parseInt(d.slice(5, 7), 10) - 1] + ' ' + d.slice(0, 4);
    }
    function back(n) { return latest ? (parseInt(latest.slice(0, 4), 10) - n) + latest.slice(4) : ''; }
    var own = m.ownership || {};
    return { latest: mo(latest), d1: mo(back(1)), d3: mo(back(3)), d10: mo(back(10)),
      own: own.label || (own.asof ? 'as of ' + own.asof : ''), since: own.recent_since || '',
      acs: 'Census ACS 2020–24', years: m.series_years || [] };
  }
  function fillDesc(t) {
    var m = capitalMeta();
    return t.replace('{own}', m.own).replace('{since}', m.since).replace('{latest}', m.latest).replace('{d1}', m.d1).replace('{d3}', m.d3).replace('{d10}', m.d10).replace(/\{acs\}/g, m.acs);
  }

  function updateCapitalLegend() {
    var def = CAPITAL_INDICATORS[state.capitalIndicator];
    var dom = def.scale.domain();
    var stops = [];
    for (var i = 0; i <= 8; i++) stops.push(def.scale(dom[0] + (dom[dom.length - 1] - dom[0]) * i / 8).hex());
    document.getElementById('capital-gradient').style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
    document.getElementById('capital-range-min').textContent = def.min;
    document.getElementById('capital-range-max').textContent = def.max;
    document.getElementById('capital-indicator-desc').textContent = fillDesc(def.desc);
  }

  function buildCapitalLayer() {
    var group = state.layerGroups.capital;
    group.clearLayers();
    var data = state.layerData.capital;
    if (!data) return;
    var key = state.capitalIndicator;
    var def = CAPITAL_INDICATORS[key];
    updateCapitalLegend();
    L.geoJSON(data, {
      style: function (f) {
        var v = f.properties[key];
        return { fillColor: v != null ? def.scale(v).hex() : NO_DATA, fillOpacity: 0.7, color: 'rgba(255,255,255,0.25)', weight: 1 };
      },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'capital'); });
        layer.bindTooltip(function () {
          return '<strong>ZIP ' + esc(f.properties.zip) + '</strong><br>' + def.short + ': ' + def.fmt(f.properties[key]);
        }, { sticky: true, className: 'dark-tooltip' });
        layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.85, weight: 2, color: 'rgba(255,255,255,0.6)' }); });
        layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.7, weight: 1, color: 'rgba(255,255,255,0.25)' }); });
      },
    }).addTo(group);
  }

  function sparkline(values, years, color, fmt) {
    var pts = values.map(function (v, i) { return v == null ? null : [i, v]; }).filter(Boolean);
    if (pts.length < 2) return '<p class="info-note">Not enough Zillow data for a trend.</p>';
    var W = 260, H = 56, pad = 4;
    var lo = Math.min.apply(null, pts.map(function (p) { return p[1]; }));
    var hi = Math.max.apply(null, pts.map(function (p) { return p[1]; }));
    var sx = function (i) { return pad + (W - 2 * pad) * i / (values.length - 1); };
    var sy = function (v) { return hi === lo ? H / 2 : H - pad - (H - 2 * pad) * (v - lo) / (hi - lo); };
    var d = pts.map(function (p, k) { return (k ? 'L' : 'M') + sx(p[0]).toFixed(1) + ' ' + sy(p[1]).toFixed(1); }).join(' ');
    var first = pts[0], last = pts[pts.length - 1];
    return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '" role="img">' +
      '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2"/>' +
      '<circle cx="' + sx(last[0]) + '" cy="' + sy(last[1]) + '" r="3" fill="' + color + '"/></svg>' +
      '<div class="spark-axis"><span>' + years[first[0]] + ': ' + fmt(first[1]) + '</span><span>' + years[last[0]] + ': ' + fmt(last[1]) + '</span></div>';
  }

  function initCapitalSelector() {
    var select = document.getElementById('capital-indicator-select');
    // Hide indicators with no data yet (e.g. ownership before the appraisal-district build has run)
    var feats = (state.layerData.capital && state.layerData.capital.features) || [];
    select.querySelectorAll('option').forEach(function (o) {
      var has = feats.some(function (f) { return f.properties[o.value] != null; });
      o.hidden = o.disabled = !has;
    });
    select.querySelectorAll('optgroup').forEach(function (g) {
      g.hidden = !g.querySelector('option:not([disabled])');
    });
    select.value = state.capitalIndicator;
    select.addEventListener('change', function () {
      state.capitalIndicator = select.value;
      if (state.activeLayers.has('capital')) buildCapitalLayer();
      else updateCapitalLegend();
    });
    if (state.layerData.capital) updateCapitalLegend();
  }


  // ── Lending (HMDA, by census tract) ────────────────────────
  var LENDING_INDICATORS = {
    investor_share: { label: 'Mortgages for investment properties', short: 'Investor loans',
      scale: chroma.scale(['#f2f0f7', '#9e9ac8', '#3f007d']).domain([0, 15, 30]), min: '0%', max: '30%+',
      desc: 'Share of home-purchase mortgages (1–4 unit homes) where the buyer said the home is an investment property. Undercounts investors, who often pay cash.' },
    denial_rate: { label: 'Mortgage denial rate', short: 'Denial rate',
      scale: chroma.scale(['#ffffcc', '#fd8d3c', '#800026']).domain([5, 15, 30]), min: '5%', max: '30%+',
      desc: 'Share of owner-occupant home-purchase applications that lenders denied.' },
    hispanic_share: { label: 'Loans to Hispanic or Latino buyers', short: 'Hispanic buyers',
      scale: chroma.scale(['#f7fbff', '#6baed6', '#08306b']).domain([0, 50, 100]), min: '0%', max: '100%',
      desc: 'Share of owner-occupant home-purchase mortgages that went to Hispanic or Latino borrowers.' },
    black_share: { label: 'Loans to Black buyers', short: 'Black buyers',
      scale: chroma.scale(['#f7fbff', '#6baed6', '#08306b']).domain([0, 50, 100]), min: '0%', max: '100%',
      desc: 'Share of owner-occupant home-purchase mortgages that went to Black borrowers.' },
  };

  function lendingYears() {
    var y = ((state.layerData.lending || {}).metadata || {}).years || [];
    return y.length ? (y.length > 1 ? y[0] + '–' + y[y.length - 1] : y[0]) : '';
  }

  function updateLendingLegend() {
    var def = LENDING_INDICATORS[state.lendingIndicator];
    var dom = def.scale.domain(), stops = [];
    for (var i = 0; i <= 8; i++) stops.push(def.scale(dom[0] + (dom[dom.length - 1] - dom[0]) * i / 8).hex());
    document.getElementById('lending-gradient').style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
    document.getElementById('lending-range-min').textContent = def.min;
    document.getElementById('lending-range-max').textContent = def.max;
    document.getElementById('lending-indicator-desc').textContent = def.desc + ' HMDA ' + lendingYears() + '.';
  }

  function buildLendingLayer() {
    var group = state.layerGroups.lending;
    group.clearLayers();
    var data = state.layerData.lending;
    if (!data) return;
    var key = state.lendingIndicator, def = LENDING_INDICATORS[key];
    updateLendingLegend();
    L.geoJSON(data, {
      style: function (f) {
        var v = f.properties[key];
        return { fillColor: v != null ? def.scale(v).hex() : NO_DATA, fillOpacity: 0.7, color: 'rgba(255,255,255,0.12)', weight: 0.6 };
      },
      onEachFeature: function (f, layer) {
        onClick(layer, function () { showInfoPanel(f, 'lending'); });
        layer.bindTooltip(function () {
          return '<strong>' + esc(f.properties.name) + '</strong><br>' + def.short + ': ' + pct(f.properties[key]) +
            ' <span class="moe">(' + (f.properties.purchase_loans || 0) + ' loans)</span>';
        }, { sticky: true, className: 'dark-tooltip' });
      },
    }).addTo(group);
  }

  function initLendingSelector() {
    var select = document.getElementById('lending-indicator-select');
    select.value = state.lendingIndicator;
    select.addEventListener('change', function () {
      state.lendingIndicator = select.value;
      if (state.activeLayers.has('lending')) buildLendingLayer(); else updateLendingLegend();
    });
    if (state.layerData.lending) updateLendingLegend();
  }

  // ── Info panel ─────────────────────────────────────────────
  function section(title, body) {
    return '<div class="info-section">' + (title ? '<h4>' + title + '</h4>' : '') + body + '</div>';
  }
  function row(label, value, style) {
    return '<div class="info-row"><span class="label">' + label + '</span><span class="value"' +
      (style ? ' style="' + style + '"' : '') + '>' + value + '</span></div>';
  }
  function note(text) { return '<p class="info-note">' + text + '</p>'; }

  var infoBuilders = {
    redlining: function (p) {
      var g = p.grade;
      var title = p.label ? 'HOLC area ' + esc(p.label) : 'HOLC area';
      var gradeText = g ? g + ' — “' + holcLabels[g] + '”' : esc(p.cat || 'Not graded');
      return '<h3>' + title + '</h3>' +
        section('HOLC map (' + HOLC_YEAR + ')', row('Grade', gradeText, 'color:' + (holcColors[g] || HOLC_UNGRADED))) +
        section('', note('The surveyors’ written area descriptions are on ' +
          link('https://dsl.richmond.edu/panorama/redlining/map/TX/Houston', 'Mapping Inequality') + '.'));
    },
    highways: function (p) {
      var dates = [];
      if (p.construction_year) dates.push(row('Construction began', p.construction_year));
      if (p.open_year) dates.push(row('First section opened', p.open_year));
      if (p.completion_year) dates.push(row('Completed', p.completion_year));
      var src = (p.sources || []).map(function (u, i) { return link(u, 'source ' + (i + 1)); }).join(' · ');
      return '<h3>' + esc(p.name) + '</h3>' +
        section('Construction', row('Route', esc(p.designation)) + dates.join('')) +
        (p.neighborhoods_displaced && p.neighborhoods_displaced.length
          ? section('Neighborhoods cut or displaced', '<p class="info-danger">' + p.neighborhoods_displaced.map(esc).join(', ') + '</p>')
          : '') +
        section('', '<p class="info-text">' + esc(p.description) + '</p>' + (src ? note(src) : ''));
    },
    income: function (p) {
      var pov = p.poverty_rate_2020;
      return '<h3>' + esc(p.name) + '</h3>' +
        section('Median household income (' + ACS_LABEL + ')', row('Income', money(p.income_2020))) +
        section('Poverty rate (' + ACS_LABEL + ')',
          row('Rate', pct(pov)) +
          (pov != null ? '<div class="info-bar"><div class="info-bar-fill" style="width:' + Math.min(100, pov) + '%;background:' +
            (pov > 30 ? 'var(--danger)' : pov > 15 ? 'var(--warning)' : 'var(--success)') + ';"></div></div>' : '')) +
        section('', note('U.S. Census Bureau, American Community Survey 5-year estimates. “No data” means the Census Bureau suppressed the estimate.'));
    },
    race: function (p) {
      var groups = [['white', 'White'], ['black', 'Black'], ['hispanic', 'Hispanic or Latino'], ['asian', 'Asian']];
      var bars = groups.map(function (g) {
        var v = p['pct_' + g[0] + '_2020'];
        return '<div style="margin:4px 0;">' + row(g[1], pct(v)) +
          '<div class="info-bar"><div class="info-bar-fill" style="width:' + (v || 0) + '%;background:' + raceColors[g[0]] + ';"></div></div></div>';
      }).join('');
      return '<h3>' + esc(p.name) + '</h3>' +
        section('Race and ethnicity (' + ACS_LABEL + ')', bars) +
        section('', note('White, Black and Asian are non-Hispanic. Census Bureau ACS 5-year estimates.'));
    },
    floods: function (p) {
      return '<h3>FEMA flood zone ' + esc(p.zone || '') + '</h3>' +
        section('Classification',
          row('Zone', esc(p.zone || '')) +
          row('Risk', esc(p.flood_risk || 'unknown'), 'color:' + (p.flood_risk === 'moderate' ? 'var(--warning)' : 'var(--danger)'))) +
        section('', '<p class="info-text">' + esc(p.zone_description || '') + '</p>' +
          note('FEMA National Flood Hazard Layer extract. For an official determination use the ' +
            link('https://msc.fema.gov/portal/home', 'FEMA Flood Map Service Center') + '.'));
    },
    pollution: function (p) {
      return '<h3>' + esc(p.facility_name || 'TRI facility') + '</h3>' +
        section('EPA Toxics Release Inventory', row('Industry', esc(p.industry || '—')) + row('TRI ID', esc(p.tri_facility_id || '—'))) +
        section('', note('Registered TRI facility. Release totals are not loaded on this map.'));
    },
    capital: function (p) {
      var m = capitalMeta();
      var I = CAPITAL_INDICATORS;
      function r(k) { return row(I[k].short, I[k].fmt(p[k]), k === state.capitalIndicator ? 'color:var(--accent);font-weight:600;' : ''); }
      return '<h3>ZIP ' + esc(p.zip) + '</h3>' +
        section('Home values (Zillow, ' + m.latest + ')', r('home_value') + r('value_change_1y') + r('value_change_10y') +
          sparkline(p.value_series || [], m.years, '#fd8d3c', function (v) { return '$' + Math.round(v / 1000) + 'K'; })) +
        section('Asking rents (Zillow, ' + m.latest + ')', r('rent') + r('rent_change_1y') + r('rent_change_3y') +
          sparkline(p.rent_series || [], m.years, '#58a6ff', function (v) { return '$' + Math.round(v).toLocaleString(); })) +
        section('Residents (' + m.acs + ')',
          row('Median household income', p.median_income != null ? money(p.median_income) + (p.median_income_moe != null ? ' <span class="moe">± ' + money(p.median_income_moe) + '</span>' : '') : 'No data') +
          r('price_to_income') + r('rent_burdened_pct') + r('renter_pct') +
          row('Population', p.population != null ? p.population.toLocaleString() : '—')) +
        (p.homes != null ? section('Single-family owners (appraisal district, ' + esc(m.own.replace('as of ', '')) + ')',
          row('Single-family homes', p.homes.toLocaleString()) + r('company_owned_pct') + r('institutional_pct') +
          (p.new_build_company ? row('New homes held by companies (excluded)', p.new_build_company.toLocaleString()) : '') +
          r('out_of_state_owner_pct') + (p.recent_sales != null ? row('Owner changes since ' + esc(m.since), p.recent_sales.toLocaleString()) + r('recent_company_pct') : '')) : '') +
        section('', note((p.acs_note ? esc(p.acs_note) + '. ' : '') +
          'Zillow figures are typical values for the ZIP in nominal dollars; asking rents reflect new leases, not what current tenants pay. ' +
          'Census figures cover the ZIP Code Tabulation Area. Sources: ' + link('https://www.zillow.com/research/data/', 'Zillow Research') +
          ', ' + link('https://censusreporter.org/tables/B25070/', 'Census ACS via Census Reporter') + '.'));
    },
    lending: function (p) {
      var bench = ((state.layerData.lending || {}).metadata || {}).county_benchmark || {};
      function r(k) {
        return row(LENDING_INDICATORS[k].short, pct(p[k]) + (bench[k] != null ? ' <span class="moe">county ' + pct(bench[k]) + '</span>' : ''),
          k === state.lendingIndicator ? 'color:var(--accent);font-weight:600;' : '');
      }
      return '<h3>' + esc(p.name) + '</h3>' +
        section('Home-purchase mortgages (HMDA ' + lendingYears() + ')',
          row('Loans originated', (p.purchase_loans || 0).toLocaleString()) + r('investor_share') + r('denial_rate') + r('hispanic_share') + r('black_share')) +
        section('', note('Home Mortgage Disclosure Act data, 1–4 unit homes. Shares are withheld where there are fewer than 20 loans or applications. ' +
          'Cash purchases are not included, so investor buying is undercounted. Source: ' + link('https://ffiec.cfpb.gov/data-browser/', 'CFPB HMDA Data Browser') + '.'));
    },
    political: function (p) {
      var c = partyColors[p.party] || partyColors.Unknown;
      return '<h3>' + esc(p.name) + '</h3>' +
        section('Officeholder',
          row('Name', esc(p.representative)) +
          row('Party', partyNames[p.party] || 'Unknown', 'color:' + c + ';font-weight:600;') +
          row('District', esc(p.district_id))) +
        section('', note((p.party === 'NP' ? 'Houston municipal elections are nonpartisan. ' : '') +
          'Officeholders as of ' + esc(p.as_of || '—') + '.'));
    },
  };

  function showInfoPanel(feature, type) {
    document.getElementById('info-content').innerHTML = infoBuilders[type](feature.properties);
    document.getElementById('info-panel').classList.remove('hidden');
  }

  // ── Timeline ───────────────────────────────────────────────
  function initTimeline() {
    var slider = document.getElementById('timeline-slider');
    var labels = document.getElementById('timeline-labels');
    var html = '';
    for (var d = DECADE_MIN; d <= DECADE_MAX; d += 10) html += '<span data-decade="' + d + '">' + d + 's</span>';
    labels.innerHTML = html;

    noUiSlider.create(slider, {
      start: [DECADE_MAX], connect: [true, false], step: 10,
      range: { min: DECADE_MIN, max: DECADE_MAX },
      format: { to: function (v) { return Math.round(v); }, from: Number },
    });
    slider.noUiSlider.on('update', function (values) {
      var decade = parseInt(values[0], 10);
      if (decade !== state.currentDecade) {
        state.currentDecade = decade;
        onDecadeChange(decade);
      }
    });
    labels.querySelectorAll('span').forEach(function (el) {
      el.addEventListener('click', function () { slider.noUiSlider.set(parseInt(el.getAttribute('data-decade'), 10)); });
    });
    updateDecadeLabels(DECADE_MAX);
  }

  function onDecadeChange(decade) {
    document.getElementById('current-decade').textContent = decade + 's';
    updateDecadeLabels(decade);
    if (state.activeLayers.has('highways')) buildHighwayLayer();
    showNarrativeForDecade(decade);
  }

  function updateDecadeLabels(decade) {
    document.querySelectorAll('#timeline-labels span').forEach(function (el) {
      el.classList.toggle('active', parseInt(el.getAttribute('data-decade'), 10) === decade);
    });
  }

  // ── Narrative cards (all events in a decade, stepped with prev/next) ──
  function eventsForDecade(decade) {
    return state.timelineEvents.filter(function (e) { return Math.floor(e.year / 10) * 10 === decade; });
  }

  function showNarrativeForDecade(decade) {
    state.narrative.decade = decade;
    state.narrative.index = 0;
    renderNarrative();
  }

  function renderNarrative() {
    var card = document.getElementById('narrative-card');
    var n = state.narrative;
    var events = eventsForDecade(n.decade);
    if (!events.length || n.dismissed.has(n.decade)) { card.classList.add('hidden'); return; }
    var e = events[n.index];
    document.getElementById('narrative-year').textContent = e.year;
    document.getElementById('narrative-title').textContent = e.title;
    document.getElementById('narrative-text').textContent = e.description;
    var srcs = [].concat(e.source || []);
    document.getElementById('narrative-source').innerHTML = srcs.map(function (u, i) {
      return link(u, srcs.length > 1 ? 'Source ' + (i + 1) : 'Source');
    }).join(' · ');
    var nav = document.getElementById('narrative-nav');
    nav.classList.toggle('hidden', events.length < 2);
    document.getElementById('narrative-count').textContent = (n.index + 1) + ' of ' + events.length;
    document.getElementById('narrative-prev').disabled = n.index === 0;
    document.getElementById('narrative-next').disabled = n.index === events.length - 1;
    card.classList.remove('hidden');
  }

  function initNarrative() {
    document.getElementById('narrative-prev').addEventListener('click', function () {
      if (state.narrative.index > 0) { state.narrative.index--; renderNarrative(); }
    });
    document.getElementById('narrative-next').addEventListener('click', function () {
      if (state.narrative.index < eventsForDecade(state.narrative.decade).length - 1) { state.narrative.index++; renderNarrative(); }
    });
    document.getElementById('narrative-close').addEventListener('click', function () {
      state.narrative.dismissed.add(state.narrative.decade);
      document.getElementById('narrative-card').classList.add('hidden');
    });
  }

  // ── Controls ───────────────────────────────────────────────
  function initLayerToggles() {
    document.querySelectorAll('.layer-toggle input').forEach(function (input) {
      input.addEventListener('change', function () {
        var name = input.getAttribute('data-layer');
        var group = input.closest('.layer-group');
        if (input.checked) {
          state.activeLayers.add(name);
          group.classList.add('active');
          builders[name]();
          state.layerGroups[name].addTo(state.map);
        } else {
          state.activeLayers.delete(name);
          group.classList.remove('active');
          document.getElementById('info-panel').classList.add('hidden');
          state.map.removeLayer(state.layerGroups[name]);
        }
      });
    });
  }

  function initPoliticalSelector() {
    var select = document.getElementById('political-type-select');
    select.addEventListener('change', function () {
      state.politicalType = select.value;
      if (state.activeLayers.has('political')) buildPoliticalLayer();
    });
  }

  function initUI() {
    document.getElementById('sidebar-toggle').addEventListener('click', function () {
      document.getElementById('sidebar').classList.toggle('open');
    });
    document.getElementById('info-close').addEventListener('click', function () {
      document.getElementById('info-panel').classList.add('hidden');
    });
    document.getElementById('about-link').addEventListener('click', function (e) {
      e.preventDefault();
      document.getElementById('about-modal').classList.remove('hidden');
    });
    document.getElementById('modal-close').addEventListener('click', function () {
      document.getElementById('about-modal').classList.add('hidden');
    });
    document.getElementById('about-modal').addEventListener('click', function (e) {
      if (e.target === this) this.classList.add('hidden');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        document.getElementById('about-modal').classList.add('hidden');
        document.getElementById('info-panel').classList.add('hidden');
      }
    });
    state.map.on('click', function () {
      document.getElementById('info-panel').classList.add('hidden');
      if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');
    });
  }

  function showLoading() {
    var o = document.createElement('div');
    o.className = 'loading-overlay';
    o.id = 'loading';
    o.innerHTML = '<div class="loading-spinner"></div><div class="loading-text">Loading map data…</div>';
    document.body.appendChild(o);
  }
  function hideLoading() {
    var o = document.getElementById('loading');
    if (o) { o.classList.add('fade-out'); setTimeout(function () { o.remove(); }, 600); }
  }

  function initLegends() {
    var stops = [];
    for (var i = 0; i <= 8; i++) stops.push(incomeScale(20000 + 230000 * i / 8).hex());
    document.getElementById('income-gradient').style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
  }

  // ── Boot ───────────────────────────────────────────────────
  function boot() {
    if (location.protocol === 'file:') {
      document.body.insertAdjacentHTML('beforeend',
        '<div class="file-warning">This map loads its data with fetch(), which browsers block for files opened directly. ' +
        'Run <code>python -m http.server 8000</code> in this folder and open <code>http://localhost:8000</code>.</div>');
    }
    showLoading();
    initMap();
    initLegends();
    loadAllData().then(function () {
      initLayerToggles();
      initTimeline();
      initNarrative();
      initPoliticalSelector();
      initCapitalSelector();
      initLendingSelector();
      initUI();
      var red = document.getElementById('layer-redlining');
      red.checked = true;
      red.dispatchEvent(new Event('change'));
      showNarrativeForDecade(state.currentDecade);
      hideLoading();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
