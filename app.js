/* ============================================================
   Houston Inequality Map — app.js
   Interactive layered map of spatial inequality across decades
   ============================================================ */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────
  const state = {
    currentDecade: 2020,
    activeLayers: new Set(),
    layerData: {},      // raw GeoJSON data keyed by layer name
    layerGroups: {},    // Leaflet layer groups keyed by layer name
    map: null,
    timelineEvents: [],
    narrativeDismissed: new Set(),
    // Capital Flow state
    capitalIndicator: 'displacement_risk',  // currently selected indicator
    capitalData: null,                       // raw GeoJSON for capital layer
    // Political Districts state
    politicalType: 'congressional',          // currently selected district type
  };

  // ── Income color scale (viridis-like) ──────────────────────
  const incomeScale = chroma.scale('viridis').domain([20000, 250000]);

  // ── Capital Flow indicator definitions ─────────────────────
  const CAPITAL_INDICATORS = {
    displacement_risk: {
      label: 'Displacement Risk',
      unit: '0-100',
      domain: [10, 90],
      scale: chroma.scale(['#1a9850', '#fee08b', '#d73027']),
      format: function (v) { return v != null ? v.toFixed(0) + '/100' : 'N/A'; },
      description: 'Composite score measuring gentrification displacement pressure',
    },
    price_trajectory: {
      label: 'Price Trajectory',
      unit: '%',
      domain: [-5, 60],
      scale: chroma.scale(['#2166ac', '#f7f7f7', '#b2182b']),
      format: function (v) { return v != null ? (v >= 0 ? '+' : '') + v.toFixed(1) + '%' : 'N/A'; },
      description: '3-year median home price growth rate',
    },
    listing_velocity: {
      label: 'Listing Velocity',
      unit: 'ratio',
      domain: [0.3, 3.0],
      scale: chroma.scale(['#4575b4', '#ffffbf', '#d73027']),
      format: function (v) { return v != null ? v.toFixed(2) + 'x' : 'N/A'; },
      description: 'New listings / active inventory ratio (market heat)',
    },
    rental_yield: {
      label: 'Rental Yield',
      unit: '%',
      domain: [2, 10],
      scale: chroma.scale(['#f1eef6', '#d7b5d8', '#980043']),
      format: function (v) { return v != null ? v.toFixed(1) + '%' : 'N/A'; },
      description: 'Gross rental yield (annual rent / home value)',
    },
    investor_activity: {
      label: 'Investor Activity',
      unit: '0-100',
      domain: [10, 80],
      scale: chroma.scale(['#edf8fb', '#b2e2e2', '#238b45']).domain([10, 45, 80]),
      format: function (v) { return v != null ? v.toFixed(0) + '/100' : 'N/A'; },
      description: 'Composite investor activity index',
    },
    dom_shift: {
      label: 'DOM Shift',
      unit: 'days',
      domain: [-20, 10],
      scale: chroma.scale(['#d73027', '#fee08b', '#1a9850']),
      format: function (v) { return v != null ? (v >= 0 ? '+' : '') + v.toFixed(0) + ' days' : 'N/A'; },
      description: 'Days-on-market change (negative = selling faster)',
    },
    flip_rate: {
      label: 'Flip Rate',
      unit: '%',
      domain: [1, 20],
      scale: chroma.scale(['#ffffcc', '#fd8d3c', '#800026']),
      format: function (v) { return v != null ? v.toFixed(1) + '%' : 'N/A'; },
      description: 'Estimated short-hold resale percentage',
    },
    affordability_cliff: {
      label: 'Affordability Cliff',
      unit: 'ratio',
      domain: [0.5, 3.5],
      scale: chroma.scale(['#1a9850', '#fee08b', '#d73027']),
      format: function (v) { return v != null ? v.toFixed(2) + 'x' : 'N/A'; },
      description: 'Home price / (4x median income) — above 1.0 = unaffordable',
    },
  };

  // ── Party colors ──────────────────────────────────────────
  const partyColors = {
    D: '#3b82f6',
    R: '#ef4444',
    Unknown: '#6b7280',
  };

  // ── Race colors ────────────────────────────────────────────
  const raceColors = {
    white: '#1b9e77',
    black: '#d95f02',
    hispanic: '#7570b3',
    asian: '#e7298a',
    diverse: '#66a61e',
  };

  // ── HOLC colors ────────────────────────────────────────────
  const holcColors = {
    A: '#4daf4a',
    B: '#377eb8',
    C: '#ffff33',
    D: '#e41a1c',
  };

  // ── Decade → income field mapping ──────────────────────────
  function incomeField(decade) {
    if (decade <= 1970) return 'income_1970';
    if (decade <= 1980) return 'income_1980';
    if (decade <= 1990) return 'income_1990';
    if (decade <= 2000) return 'income_2000';
    if (decade <= 2010) return 'income_2010';
    return 'income_2020';
  }

  // ── Decade → race field suffix ─────────────────────────────
  function raceSuffix(decade) {
    if (decade <= 1970) return '_1970';
    if (decade <= 1990) return '_1990';
    return '_2020';
  }

  // ── Helpers ────────────────────────────────────────────────
  function formatMoney(n) {
    if (n >= 1000) return '$' + Math.round(n / 1000) + 'K';
    return '$' + n;
  }

  function pct(v) {
    return (v != null ? v.toFixed(1) : '—') + '%';
  }

  // ── Initialize Map ─────────────────────────────────────────
  function initMap() {
    state.map = L.map('map', {
      center: [29.76, -95.37],
      zoom: 11,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(state.map);

    // Initialize empty layer groups
    const layerNames = ['redlining', 'highways', 'income', 'race', 'floods', 'pollution', 'capital', 'political'];
    layerNames.forEach(name => {
      state.layerGroups[name] = L.layerGroup();
    });
  }

  // ── Data Loading ───────────────────────────────────────────
  async function loadAllData() {
    const loads = [
      fetch('data/redlining/houston_holc.geojson').then(r => r.json()).then(d => { state.layerData.redlining = d; }),
      fetch('data/infrastructure/highways.geojson').then(r => r.json()).then(d => { state.layerData.highways = d; }),
      fetch('data/census/income_2020.geojson').then(r => r.json()).then(d => { state.layerData.income = d; }),
      fetch('data/census/race_2020.geojson').then(r => r.json()).then(d => { state.layerData.race = d; }),
      fetch('data/environment/flood_zones.geojson').then(r => r.json()).then(d => { state.layerData.floods = d; }),
      fetch('data/environment/tri_sites.geojson').then(r => r.json()).then(d => { state.layerData.pollution = d; }),
      fetch('data/annotations/timeline_events.json').then(r => r.json()).then(d => { state.timelineEvents = d; }),
      fetch('data/capital/houston_capital.geojson').then(r => r.json()).then(d => { state.layerData.capital = d; state.capitalData = d; }),
      fetch('data/political/districts.geojson').then(r => r.json()).then(d => { state.layerData.political = d; }),
    ];

    const results = await Promise.allSettled(loads);
    results.forEach((r, i) => {
      if (r.status === 'rejected') {
        console.warn('Failed to load data:', r.reason);
      }
    });
  }

  // ── Build Layers ───────────────────────────────────────────

  function buildRedliningLayer() {
    const group = state.layerGroups.redlining;
    group.clearLayers();
    const data = state.layerData.redlining;
    if (!data) return;

    L.geoJSON(data, {
      style: function (feature) {
        const grade = feature.properties.holc_grade;
        return {
          fillColor: holcColors[grade] || '#888',
          fillOpacity: 0.35,
          color: holcColors[grade] || '#888',
          weight: 1.5,
          opacity: 0.8,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function () {
          showInfoPanel(feature, 'redlining');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.55, weight: 2.5 });
        });
        layer.on('mouseout', function () {
          layer.setStyle({ fillOpacity: 0.35, weight: 1.5 });
        });
      },
    }).addTo(group);
  }

  function buildHighwayLayer() {
    const group = state.layerGroups.highways;
    group.clearLayers();
    const data = state.layerData.highways;
    if (!data) return;

    const decade = state.currentDecade;

    data.features.forEach(function (feature) {
      const props = feature.properties;
      const builtDecade = parseInt(props.decade) || props.construction_year;
      const constructionDecadeStart = Math.floor(props.construction_year / 10) * 10;

      // Only show highways built by the current decade
      if (constructionDecadeStart > decade) return;

      // Determine opacity: newer highways are slightly dimmer when viewing earlier decades
      const age = decade - constructionDecadeStart;
      const opacity = age >= 20 ? 0.9 : 0.7;

      // Highway line
      const line = L.geoJSON(feature, {
        style: {
          color: '#ff8c00',
          weight: 3,
          opacity: opacity,
          dashArray: constructionDecadeStart === decade ? '8 6' : null,
        },
        onEachFeature: function (feat, layer) {
          layer.on('click', function () {
            showInfoPanel(feat, 'highways');
          });
        },
      });
      line.addTo(group);

      // Buffer zone (displacement area) — draw a thicker semi-transparent line
      if (props.neighborhoods_displaced && props.neighborhoods_displaced.length > 0) {
        const buffer = L.geoJSON(feature, {
          style: {
            color: '#ff8c00',
            weight: 18,
            opacity: 0.08,
            lineCap: 'round',
            lineJoin: 'round',
          },
          interactive: false,
        });
        buffer.addTo(group);
      }

      // Label
      let labelCoords;
      if (feature.geometry.type === 'MultiLineString') {
        // Pick the longest line segment and use its midpoint
        const lines = feature.geometry.coordinates;
        let longest = lines[0];
        for (let k = 1; k < lines.length; k++) {
          if (lines[k].length > longest.length) longest = lines[k];
        }
        labelCoords = longest[Math.floor(longest.length / 2)];
      } else {
        const coords = feature.geometry.coordinates;
        labelCoords = coords[Math.floor(coords.length / 2)];
      }
      if (labelCoords) {
        const label = L.marker([labelCoords[1], labelCoords[0]], {
          icon: L.divIcon({
            className: 'highway-label',
            html: '<span style="background:rgba(13,17,23,0.85);color:#ff8c00;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600;white-space:nowrap;font-family:Inter,sans-serif;">' + props.designation + '</span>',
            iconSize: null,
          }),
          interactive: false,
        });
        label.addTo(group);
      }
    });
  }

  function buildIncomeLayer() {
    const group = state.layerGroups.income;
    group.clearLayers();
    const data = state.layerData.income;
    if (!data) return;

    const field = incomeField(state.currentDecade);

    L.geoJSON(data, {
      style: function (feature) {
        const income = feature.properties[field];
        const color = income ? incomeScale(income).hex() : '#333';
        return {
          fillColor: color,
          fillOpacity: 0.6,
          color: 'rgba(255,255,255,0.15)',
          weight: 1,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function () {
          showInfoPanel(feature, 'income');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.8, weight: 2, color: 'rgba(255,255,255,0.4)' });
          const income = feature.properties[field];
          layer.bindTooltip(
            '<strong>' + feature.properties.name + '</strong><br>' +
            'Income: ' + (income ? '$' + income.toLocaleString() : 'N/A'),
            { sticky: true, className: 'dark-tooltip' }
          ).openTooltip();
        });
        layer.on('mouseout', function () {
          layer.setStyle({ fillOpacity: 0.6, weight: 1, color: 'rgba(255,255,255,0.15)' });
          layer.unbindTooltip();
        });
      },
    }).addTo(group);
  }

  function buildRaceLayer() {
    const group = state.layerGroups.race;
    group.clearLayers();
    const data = state.layerData.race;
    if (!data) return;

    const suffix = raceSuffix(state.currentDecade);

    L.geoJSON(data, {
      style: function (feature) {
        const p = feature.properties;
        const w = p['pct_white' + suffix] || 0;
        const b = p['pct_black' + suffix] || 0;
        const h = p['pct_hispanic' + suffix] || 0;
        const a = p['pct_asian' + suffix] || 0;

        let dominant = 'diverse';
        const max = Math.max(w, b, h, a);
        if (max >= 50) {
          if (w === max) dominant = 'white';
          else if (b === max) dominant = 'black';
          else if (h === max) dominant = 'hispanic';
          else if (a === max) dominant = 'asian';
        }

        return {
          fillColor: raceColors[dominant],
          fillOpacity: 0.5,
          color: 'rgba(255,255,255,0.1)',
          weight: 1,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function () {
          showInfoPanel(feature, 'race');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.75, weight: 2, color: 'rgba(255,255,255,0.3)' });
          const p = feature.properties;
          const s = raceSuffix(state.currentDecade);
          layer.bindTooltip(
            '<strong>' + p.name + '</strong><br>' +
            'W: ' + pct(p['pct_white' + s]) +
            ' B: ' + pct(p['pct_black' + s]) +
            ' H: ' + pct(p['pct_hispanic' + s]) +
            ' A: ' + pct(p['pct_asian' + s]),
            { sticky: true, className: 'dark-tooltip' }
          ).openTooltip();
        });
        layer.on('mouseout', function () {
          layer.setStyle({ fillOpacity: 0.5, weight: 1, color: 'rgba(255,255,255,0.1)' });
          layer.unbindTooltip();
        });
      },
    }).addTo(group);
  }

  function buildFloodLayer() {
    const group = state.layerGroups.floods;
    group.clearLayers();
    const data = state.layerData.floods;
    if (!data) return;

    L.geoJSON(data, {
      style: function (feature) {
        const risk = feature.properties.flood_risk;
        const isModerate = feature.properties.zone === 'X500' || feature.properties.flood_risk === 'moderate';
        return {
          fillColor: risk === 'coastal' ? '#0066cc' : '#0064ff',
          fillOpacity: isModerate ? 0.1 : (risk === 'high' ? 0.3 : 0.15),
          color: '#0088ff',
          weight: isModerate ? 0.5 : 1,
          opacity: 0.5,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function () {
          showInfoPanel(feature, 'floods');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.5, weight: 2 });
        });
        layer.on('mouseout', function () {
          const risk = feature.properties.flood_risk;
          const isModerate = feature.properties.zone === 'X500' || feature.properties.flood_risk === 'moderate';
          layer.setStyle({
            fillOpacity: isModerate ? 0.1 : (risk === 'high' ? 0.3 : 0.15),
            weight: isModerate ? 0.5 : 1,
          });
        });
      },
    }).addTo(group);
  }

  function buildPollutionLayer() {
    const group = state.layerGroups.pollution;
    group.clearLayers();
    const data = state.layerData.pollution;
    if (!data) return;

    const decade = state.currentDecade;

    data.features.forEach(function (feature) {
      const p = feature.properties;
      // TRI reporting started in 1987 — only show if decade >= 1980s
      if (decade < 1980) return;
      // Only show if facility existed by this decade
      const firstDecade = Math.floor(p.year_first_reported / 10) * 10;
      if (firstDecade > decade) return;

      const coords = feature.geometry.coordinates;
      const isCarcinogen = p.carcinogen;
      const radius = Math.max(6, Math.min(18, Math.sqrt(p.total_releases_lbs / 10000)));

      const marker = L.circleMarker([coords[1], coords[0]], {
        radius: radius,
        fillColor: isCarcinogen ? '#ff4444' : '#ff8c00',
        fillOpacity: 0.7,
        color: isCarcinogen ? '#ff6666' : '#ffaa44',
        weight: 1.5,
        opacity: 0.9,
      });

      marker.on('click', function () {
        showInfoPanel(feature, 'pollution');
      });

      marker.on('mouseover', function () {
        marker.setStyle({ fillOpacity: 1, radius: radius + 3 });
        marker.bindTooltip(
          '<strong>' + p.facility_name + '</strong><br>' +
          p.top_chemical + (isCarcinogen ? ' (carcinogen)' : '') + '<br>' +
          p.total_releases_lbs.toLocaleString() + ' lbs/yr',
          { className: 'dark-tooltip' }
        ).openTooltip();
      });

      marker.on('mouseout', function () {
        marker.setStyle({ fillOpacity: 0.7, radius: radius });
        marker.unbindTooltip();
      });

      marker.addTo(group);
    });
  }

  // ── Capital Flow Layer ────────────────────────────────────
  function buildCapitalLayer() {
    const group = state.layerGroups.capital;
    group.clearLayers();
    const data = state.layerData.capital;
    if (!data) return;

    const indicatorKey = state.capitalIndicator;
    const indDef = CAPITAL_INDICATORS[indicatorKey];
    if (!indDef) return;

    const scale = indDef.scale.domain(indDef.domain);

    L.geoJSON(data, {
      style: function (feature) {
        const val = feature.properties[indicatorKey];
        const color = val != null ? scale(val).hex() : '#333';
        return {
          fillColor: color,
          fillOpacity: 0.65,
          color: 'rgba(255,255,255,0.2)',
          weight: 1.5,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function () {
          showInfoPanel(feature, 'capital');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.85, weight: 2.5, color: 'rgba(255,255,255,0.5)' });
          var p = feature.properties;
          var val = p[indicatorKey];
          layer.bindTooltip(
            '<strong>' + p.zip + ' — ' + p.name + '</strong><br>' +
            indDef.label + ': <strong>' + indDef.format(val) + '</strong>',
            { sticky: true, className: 'dark-tooltip' }
          ).openTooltip();
        });
        layer.on('mouseout', function () {
          layer.setStyle({ fillOpacity: 0.65, weight: 1.5, color: 'rgba(255,255,255,0.2)' });
          layer.unbindTooltip();
        });
      },
    }).addTo(group);

    // Update the legend gradient
    updateCapitalLegend(indicatorKey);
  }

  function updateCapitalLegend(indicatorKey) {
    var indDef = CAPITAL_INDICATORS[indicatorKey];
    if (!indDef) return;

    var gradient = document.getElementById('capital-gradient');
    if (gradient) {
      var d = indDef.domain;
      var steps = 8;
      var colors = [];
      for (var i = 0; i <= steps; i++) {
        var val = d[0] + (d[d.length - 1] - d[0]) * (i / steps);
        colors.push(indDef.scale.domain(d)(val).hex());
      }
      gradient.style.background = 'linear-gradient(to right, ' + colors.join(', ') + ')';
    }

    var rangeMin = document.getElementById('capital-range-min');
    var rangeMax = document.getElementById('capital-range-max');
    if (rangeMin && rangeMax) {
      var d = indDef.domain;
      rangeMin.textContent = indDef.format(d[0]);
      rangeMax.textContent = indDef.format(d[d.length - 1]);
    }

    var descEl = document.getElementById('capital-indicator-desc');
    if (descEl) {
      descEl.textContent = indDef.description;
    }
  }

  // ── Political Districts Layer ─────────────────────────────
  function buildPoliticalLayer() {
    var group = state.layerGroups.political;
    group.clearLayers();
    var data = state.layerData.political;
    if (!data) return;

    var selectedType = state.politicalType;

    // Filter features by selected district type
    var filtered = {
      type: 'FeatureCollection',
      features: data.features.filter(function (f) {
        return f.properties.district_type === selectedType;
      }),
    };

    // Assign distinct hue per district so adjacent ones are distinguishable
    var districtCount = filtered.features.length;

    L.geoJSON(filtered, {
      style: function (feature) {
        var party = feature.properties.party;
        var color = partyColors[party] || partyColors.Unknown;
        return {
          fillColor: color,
          fillOpacity: 0.08,
          color: color,
          weight: 3,
          opacity: 0.9,
          dashArray: '6 4',
        };
      },
      onEachFeature: function (feature, layer) {
        // Add a district label at centroid
        var bounds = layer.getBounds();
        var center = bounds.getCenter();
        var p = feature.properties;
        var partyColor = partyColors[p.party] || partyColors.Unknown;
        var labelText = p.district_number || p.district_id;
        var label = L.marker(center, {
          icon: L.divIcon({
            className: 'political-label',
            html: '<span style="background:rgba(13,17,23,0.85);color:' + partyColor +
              ';padding:2px 6px;border-radius:3px;font-size:11px;font-weight:700;' +
              'white-space:nowrap;font-family:Inter,sans-serif;border:1px solid ' + partyColor + ';">' +
              labelText + '</span>',
            iconSize: null,
          }),
          interactive: false,
        });
        label.addTo(group);

        layer.on('click', function () {
          showInfoPanel(feature, 'political');
        });
        layer.on('mouseover', function () {
          layer.setStyle({ fillOpacity: 0.25, weight: 4, dashArray: null });
          layer.bindTooltip(
            '<strong>' + p.name + '</strong><br>' +
            '<span style="color:' + partyColor + '">' + p.representative + ' (' + p.party + ')</span>',
            { sticky: true, className: 'dark-tooltip' }
          ).openTooltip();
        });
        layer.on('mouseout', function () {
          layer.setStyle({ fillOpacity: 0.08, weight: 3, dashArray: '6 4' });
          layer.unbindTooltip();
        });
      },
    }).addTo(group);
  }

  // ── Layer rebuild dispatcher ───────────────────────────────
  const builders = {
    redlining: buildRedliningLayer,
    highways: buildHighwayLayer,
    income: buildIncomeLayer,
    race: buildRaceLayer,
    floods: buildFloodLayer,
    pollution: buildPollutionLayer,
    capital: buildCapitalLayer,
    political: buildPoliticalLayer,
  };

  function rebuildLayer(name) {
    if (builders[name]) builders[name]();
  }

  function rebuildAllActive() {
    state.activeLayers.forEach(function (name) {
      rebuildLayer(name);
    });
  }

  // ── Info Panel ─────────────────────────────────────────────
  function showInfoPanel(feature, layerType) {
    const panel = document.getElementById('info-panel');
    const content = document.getElementById('info-content');
    const p = feature.properties;
    let html = '';

    switch (layerType) {
      case 'redlining':
        html = buildRedliningInfo(p);
        break;
      case 'highways':
        html = buildHighwayInfo(p);
        break;
      case 'income':
        html = buildIncomeInfo(p);
        break;
      case 'race':
        html = buildRaceInfo(p);
        break;
      case 'floods':
        html = buildFloodInfo(p);
        break;
      case 'pollution':
        html = buildPollutionInfo(p);
        break;
      case 'capital':
        html = buildCapitalInfo(p);
        break;
      case 'political':
        html = buildPoliticalInfo(p);
        break;
    }

    content.innerHTML = html;
    panel.classList.remove('hidden');
  }

  function buildRedliningInfo(p) {
    const gradeLabels = { A: 'Best', B: 'Still Desirable', C: 'Declining', D: 'Hazardous' };
    const grade = p.holc_grade;
    return '' +
      '<h3>' + (p.neighborhood_name || p.holc_id) + '</h3>' +
      '<div class="info-section">' +
        '<h4>HOLC Grade (1940)</h4>' +
        '<div class="info-row"><span class="label">Grade</span>' +
        '<span class="value" style="color:' + holcColors[grade] + '">' + grade + ' — ' + gradeLabels[grade] + '</span></div>' +
      '</div>' +
      '<div class="info-section">' +
        '<h4>Assessment</h4>' +
        '<p style="font-size:12px;color:var(--text-muted);line-height:1.5;">' + (p.area_description || 'No description available.') + '</p>' +
      '</div>';
  }

  function buildHighwayInfo(p) {
    return '' +
      '<h3>' + p.name + '</h3>' +
      '<div class="info-section">' +
        '<h4>Construction</h4>' +
        '<div class="info-row"><span class="label">Route</span><span class="value">' + p.designation + '</span></div>' +
        '<div class="info-row"><span class="label">Built</span><span class="value">' + p.construction_year + '–' + p.completion_year + '</span></div>' +
        '<div class="info-row"><span class="label">Decade</span><span class="value">' + p.decade + '</span></div>' +
      '</div>' +
      (p.neighborhoods_displaced && p.neighborhoods_displaced.length > 0 ?
        '<div class="info-section">' +
          '<h4>Communities Displaced</h4>' +
          '<p style="font-size:12px;color:var(--danger);line-height:1.5;">' +
            p.neighborhoods_displaced.join(', ') +
          '</p>' +
        '</div>' : '') +
      '<div class="info-section">' +
        '<p style="font-size:12px;color:var(--text-muted);line-height:1.5;">' + (p.description || '') + '</p>' +
      '</div>';
  }

  function buildIncomeInfo(p) {
    const decades = [1970, 1980, 1990, 2000, 2010, 2020];
    let sparkHtml = '<div style="display:flex;align-items:flex-end;gap:3px;height:48px;margin:8px 0;">';
    const maxIncome = Math.max.apply(null, decades.map(function (d) { return p['income_' + d] || 0; }));

    decades.forEach(function (d) {
      const val = p['income_' + d] || 0;
      const h = maxIncome > 0 ? Math.max(4, (val / maxIncome) * 44) : 4;
      const isActive = (d === Math.floor(state.currentDecade / 10) * 10) || (state.currentDecade >= 2020 && d === 2020);
      sparkHtml += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;">' +
        '<div style="width:100%;height:' + h + 'px;background:' + (isActive ? 'var(--accent)' : '#30363d') +
        ';border-radius:2px;transition:height 0.3s ease,background 0.3s ease;"></div>' +
        '<span style="font-size:9px;color:var(--text-dim);">' + (d + '').slice(2) + '</span>' +
      '</div>';
    });
    sparkHtml += '</div>';

    return '' +
      '<h3>' + p.name + '</h3>' +
      '<div class="info-section">' +
        '<h4>Median Household Income</h4>' +
        '<div class="info-row"><span class="label">Current (' + incomeField(state.currentDecade).replace('income_', '') + ')</span>' +
        '<span class="value">$' + (p[incomeField(state.currentDecade)] || 0).toLocaleString() + '</span></div>' +
        sparkHtml +
      '</div>' +
      '<div class="info-section">' +
        '<h4>Poverty Rate (2020)</h4>' +
        '<div class="info-row"><span class="label">Rate</span><span class="value">' + pct(p.poverty_rate_2020) + '</span></div>' +
        '<div class="info-bar"><div class="info-bar-fill" style="width:' + Math.min(100, p.poverty_rate_2020 || 0) + '%;background:' +
        (p.poverty_rate_2020 > 30 ? 'var(--danger)' : p.poverty_rate_2020 > 15 ? 'var(--warning)' : 'var(--success)') + ';"></div></div>' +
      '</div>' +
      '<div class="info-section"><p style="font-size:11px;color:var(--text-dim);font-style:italic;">' +
      (p.is_sample_data ? 'Sample data for illustration' : '2020 values from ACS 2022 5-Year Estimates; historical decades are modeled') +
      '</p></div>';
  }

  function buildRaceInfo(p) {
    const s = raceSuffix(state.currentDecade);
    const suffix1970 = '_1970';
    const groups = [
      { key: 'white', label: 'White', color: raceColors.white },
      { key: 'black', label: 'Black', color: raceColors.black },
      { key: 'hispanic', label: 'Hispanic', color: raceColors.hispanic },
      { key: 'asian', label: 'Asian', color: raceColors.asian },
    ];

    let barsHtml = '';
    groups.forEach(function (g) {
      const val = p['pct_' + g.key + s] || 0;
      barsHtml +=
        '<div style="margin:4px 0;">' +
          '<div class="info-row"><span class="label">' + g.label + '</span><span class="value">' + pct(val) + '</span></div>' +
          '<div class="info-bar"><div class="info-bar-fill" style="width:' + val + '%;background:' + g.color + ';"></div></div>' +
        '</div>';
    });

    // Show change from 1970 if available
    let changeHtml = '';
    if (s !== suffix1970 && p['pct_white_1970'] != null) {
      changeHtml = '<div class="info-section"><h4>Change since 1970</h4>';
      groups.forEach(function (g) {
        const old = p['pct_' + g.key + '_1970'] || 0;
        const cur = p['pct_' + g.key + s] || 0;
        const diff = cur - old;
        const sign = diff >= 0 ? '+' : '';
        changeHtml += '<div class="info-row"><span class="label">' + g.label + '</span>' +
          '<span class="value" style="color:' + (Math.abs(diff) > 10 ? 'var(--warning)' : 'var(--text-muted)') + '">' +
          sign + diff.toFixed(1) + '%</span></div>';
      });
      changeHtml += '</div>';
    }

    return '' +
      '<h3>' + p.name + '</h3>' +
      '<div class="info-section">' +
        '<h4>Demographics (' + s.replace('_', '') + ')</h4>' +
        barsHtml +
      '</div>' +
      changeHtml +
      '<div class="info-section"><p style="font-size:11px;color:var(--text-dim);font-style:italic;">' +
      (p.is_sample_data ? 'Sample data for illustration' : '2020 values from ACS 2022 5-Year Estimates; historical decades are modeled') +
      '</p></div>';
  }

  function buildPoliticalInfo(p) {
    var partyColor = partyColors[p.party] || partyColors.Unknown;
    var partyName = p.party === 'D' ? 'Democrat' : p.party === 'R' ? 'Republican' : 'Unknown';
    var levelLabel = {
      federal: 'Federal',
      state: 'State',
      county: 'County',
      city: 'City',
    }[p.level] || p.level;

    return '' +
      '<h3>' + p.name + '</h3>' +
      '<div class="info-section">' +
        '<h4>Representative</h4>' +
        '<div class="info-row"><span class="label">Name</span>' +
        '<span class="value">' + p.representative + '</span></div>' +
        '<div class="info-row"><span class="label">Party</span>' +
        '<span class="value" style="color:' + partyColor + ';font-weight:600;">' + partyName + '</span></div>' +
        '<div class="info-row"><span class="label">Level</span>' +
        '<span class="value">' + levelLabel + '</span></div>' +
        '<div class="info-row"><span class="label">District</span>' +
        '<span class="value">' + p.district_id + '</span></div>' +
      '</div>';
  }

  function buildFloodInfo(p) {
    return '' +
      '<h3>Flood Zone ' + (p.zone || '') + (p.name ? ' — ' + p.name : '') + '</h3>' +
      '<div class="info-section">' +
        '<h4>Classification</h4>' +
        '<div class="info-row"><span class="label">Zone</span><span class="value">' + (p.zone || '') + '</span></div>' +
        '<div class="info-row"><span class="label">Risk Level</span><span class="value" style="color:' +
          (p.flood_risk === 'high' || p.flood_risk === 'coastal' ? 'var(--danger)' : 'var(--warning)') + '">' +
          (p.flood_risk || 'unknown') + '</span></div>' +
        (p.bayou ? '<div class="info-row"><span class="label">Waterway</span><span class="value">' + p.bayou + '</span></div>' : '') +
      '</div>' +
      '<div class="info-section">' +
        '<h4>Description</h4>' +
        '<p style="font-size:12px;color:var(--text-muted);line-height:1.5;">' + (p.zone_description || '') + '</p>' +
      '</div>' +
      (p.major_flood_events && p.major_flood_events.length > 0 ?
        '<div class="info-section">' +
          '<h4>Major Flood Events</h4>' +
          '<p style="font-size:12px;color:var(--text-muted);">' + p.major_flood_events.join(', ') + '</p>' +
        '</div>' : '') +
      (p.harvey_inundated !== undefined ?
        '<div class="info-section">' +
          '<div class="info-row"><span class="label">Harvey (2017)</span><span class="value" style="color:' +
          (p.harvey_inundated ? 'var(--danger)' : 'var(--success)') + '">' +
          (p.harvey_inundated ? 'Inundated' : 'Not flooded') + '</span></div>' +
        '</div>' : '');
  }

  function buildPollutionInfo(p) {
    return '' +
      '<h3>' + p.facility_name + '</h3>' +
      '<div class="info-section">' +
        '<h4>Facility Details</h4>' +
        '<div class="info-row"><span class="label">Industry</span><span class="value">' + (p.industry || 'N/A') + '</span></div>' +
        '<div class="info-row"><span class="label">Reporting since</span><span class="value">' + (p.year_first_reported || 'N/A') + '</span></div>' +
        '<div class="info-row"><span class="label">Risk Score</span><span class="value" style="color:' +
          (p.risk_score >= 8 ? 'var(--danger)' : p.risk_score >= 5 ? 'var(--warning)' : 'var(--text)') + '">' +
          p.risk_score + '/10</span></div>' +
      '</div>' +
      '<div class="info-section">' +
        '<h4>Toxic Releases</h4>' +
        '<div class="info-row"><span class="label">Total releases</span><span class="value">' + (p.total_releases_lbs || 0).toLocaleString() + ' lbs/yr</span></div>' +
        '<div class="info-row"><span class="label">Top chemical</span><span class="value">' + (p.top_chemical || 'N/A') + '</span></div>' +
        '<div class="info-row"><span class="label">Carcinogen</span><span class="value" style="color:' +
          (p.carcinogen ? 'var(--danger)' : 'var(--success)') + '">' +
          (p.carcinogen ? 'Yes' : 'No') + '</span></div>' +
      '</div>' +
      (p.nearby_neighborhoods && p.nearby_neighborhoods.length > 0 ?
        '<div class="info-section">' +
          '<h4>Nearby Communities</h4>' +
          '<p style="font-size:12px;color:var(--text-muted);">' + p.nearby_neighborhoods.join(', ') + '</p>' +
        '</div>' : '');
  }

  function buildCapitalInfo(p) {
    // ── Header ──
    var html = '<h3>' + p.zip + ' — ' + (p.name || '') + '</h3>';

    // ── Displacement Risk (hero metric) ──
    var risk = p.displacement_risk;
    var riskColor = risk >= 70 ? 'var(--danger)' : risk >= 40 ? 'var(--warning)' : 'var(--success)';
    var riskLabel = risk >= 70 ? 'High Risk' : risk >= 40 ? 'Moderate Risk' : 'Lower Risk';
    html += '<div class="info-section capital-hero">' +
      '<h4>Displacement Risk Score</h4>' +
      '<div style="display:flex;align-items:center;gap:12px;margin:6px 0;">' +
        '<span class="capital-score" style="color:' + riskColor + ';font-size:28px;font-weight:700;">' +
          (risk != null ? risk.toFixed(0) : '—') +
        '</span>' +
        '<div style="flex:1;">' +
          '<div class="info-bar" style="height:8px;"><div class="info-bar-fill" style="width:' + (risk || 0) +
          '%;background:' + riskColor + ';"></div></div>' +
          '<span style="font-size:11px;color:' + riskColor + ';">' + riskLabel + '</span>' +
        '</div>' +
      '</div>' +
    '</div>';

    // ── All 8 Indicators ──
    html += '<div class="info-section">' +
      '<h4>Capital Flow Indicators</h4>';

    var indicators = [
      ['listing_velocity', 'Listing Velocity'],
      ['price_trajectory', 'Price Trajectory'],
      ['rental_yield', 'Rental Yield'],
      ['investor_activity', 'Investor Activity'],
      ['dom_shift', 'DOM Shift'],
      ['flip_rate', 'Flip Rate'],
      ['affordability_cliff', 'Affordability'],
    ];

    indicators.forEach(function (item) {
      var key = item[0];
      var label = item[1];
      var def = CAPITAL_INDICATORS[key];
      var val = p[key];
      var formatted = def ? def.format(val) : (val != null ? val : 'N/A');
      var isActive = key === state.capitalIndicator;

      html += '<div class="info-row' + (isActive ? ' capital-active-indicator' : '') + '">' +
        '<span class="label">' + label + '</span>' +
        '<span class="value">' + formatted + '</span>' +
      '</div>';
    });

    html += '</div>';

    // ── Socioeconomic Context ──
    html += '<div class="info-section">' +
      '<h4>Socioeconomic Context</h4>' +
      '<div class="info-row"><span class="label">Median Income</span><span class="value">' +
        (p.median_household_income ? '$' + Math.round(p.median_household_income).toLocaleString() : 'N/A') + '</span></div>' +
      '<div class="info-row"><span class="label">Median Home Value</span><span class="value">' +
        (p.median_home_value ? '$' + Math.round(p.median_home_value).toLocaleString() : 'N/A') + '</span></div>' +
      '<div class="info-row"><span class="label">Median Rent</span><span class="value">' +
        (p.median_gross_rent ? '$' + Math.round(p.median_gross_rent).toLocaleString() + '/mo' : 'N/A') + '</span></div>' +
      '<div class="info-row"><span class="label">Renter Share</span><span class="value">' +
        (p.renter_pct != null ? p.renter_pct.toFixed(0) + '%' : 'N/A') + '</span></div>' +
      '<div class="info-row"><span class="label">Rent Burden</span><span class="value" style="color:' +
        (p.rent_burden_pct > 35 ? 'var(--danger)' : p.rent_burden_pct > 25 ? 'var(--warning)' : 'var(--text)') + '">' +
        (p.rent_burden_pct != null ? p.rent_burden_pct.toFixed(0) + '% of income' : 'N/A') + '</span></div>' +
      '<div class="info-row"><span class="label">Population</span><span class="value">' +
        (p.total_population ? Math.round(p.total_population).toLocaleString() : 'N/A') + '</span></div>' +
    '</div>';

    // ── Sparkline: mini indicator bar chart ──
    html += '<div class="info-section">' +
      '<h4>Indicator Profile</h4>' +
      '<div class="capital-spark">';

    var sparkIndicators = ['listing_velocity', 'price_trajectory', 'rental_yield', 'investor_activity', 'displacement_risk', 'flip_rate', 'affordability_cliff'];
    sparkIndicators.forEach(function (key) {
      var def = CAPITAL_INDICATORS[key];
      var val = p[key];
      var d = def.domain;
      var pctVal = val != null ? Math.max(0, Math.min(100, ((val - d[0]) / (d[d.length - 1] - d[0])) * 100)) : 0;
      var color = val != null ? def.scale.domain(d)(val).hex() : '#333';

      html += '<div class="capital-spark-bar">' +
        '<div class="capital-spark-fill" style="height:' + pctVal + '%;background:' + color + ';"></div>' +
        '<span class="capital-spark-label">' + def.label.substring(0, 3) + '</span>' +
      '</div>';
    });

    html += '</div></div>';

    if (p.is_sample_data) {
      html += '<div class="info-section"><p style="font-size:11px;color:var(--text-dim);font-style:italic;">Sample data for illustration. Run the data pipeline for real values.</p></div>';
    }

    return html;
  }

  // ── Capital Indicator Selector ──────────────────────────────
  function initCapitalSelector() {
    var select = document.getElementById('capital-indicator-select');
    if (!select) return;

    select.addEventListener('change', function () {
      state.capitalIndicator = select.value;
      if (state.activeLayers.has('capital')) {
        buildCapitalLayer();
      }
    });
  }

  // ── Political District Type Selector ────────────────────────
  function initPoliticalSelector() {
    var select = document.getElementById('political-type-select');
    if (!select) return;

    select.addEventListener('change', function () {
      state.politicalType = select.value;
      if (state.activeLayers.has('political')) {
        buildPoliticalLayer();
      }
    });
  }

  // ── Timeline ───────────────────────────────────────────────
  function initTimeline() {
    var slider = document.getElementById('timeline-slider');

    noUiSlider.create(slider, {
      start: [2020],
      connect: [true, false],
      step: 10,
      range: {
        min: 1940,
        max: 2020,
      },
      format: {
        to: function (value) { return Math.round(value); },
        from: function (value) { return Number(value); },
      },
    });

    slider.noUiSlider.on('update', function (values) {
      var decade = parseInt(values[0]);
      if (decade !== state.currentDecade) {
        state.currentDecade = decade;
        onDecadeChange(decade);
      }
    });

    // Clickable decade labels
    document.querySelectorAll('#timeline-labels span').forEach(function (el) {
      el.addEventListener('click', function () {
        var decade = parseInt(el.getAttribute('data-decade'));
        slider.noUiSlider.set(decade);
      });
    });

    updateDecadeLabels(2020);
  }

  function onDecadeChange(decade) {
    document.getElementById('current-decade').textContent = decade + 's';
    updateDecadeLabels(decade);

    // Rebuild decade-sensitive layers
    if (state.activeLayers.has('highways')) buildHighwayLayer();
    if (state.activeLayers.has('income')) buildIncomeLayer();
    if (state.activeLayers.has('race')) buildRaceLayer();
    if (state.activeLayers.has('pollution')) buildPollutionLayer();

    // Show narrative for this decade
    showNarrativeForDecade(decade);
  }

  function updateDecadeLabels(decade) {
    document.querySelectorAll('#timeline-labels span').forEach(function (el) {
      var d = parseInt(el.getAttribute('data-decade'));
      el.classList.toggle('active', d === decade);
    });
  }

  // ── Narrative Cards ────────────────────────────────────────
  function showNarrativeForDecade(decade) {
    var events = state.timelineEvents.filter(function (e) {
      var eventDecade = Math.floor(e.year / 10) * 10;
      return eventDecade === decade && !state.narrativeDismissed.has(e.year + ':' + e.title);
    });

    if (events.length === 0) {
      document.getElementById('narrative-card').classList.add('hidden');
      return;
    }

    // Show the first matching event
    var event = events[0];
    document.getElementById('narrative-year').textContent = event.year;
    document.getElementById('narrative-title').textContent = event.title;
    document.getElementById('narrative-text').textContent = event.description;
    document.getElementById('narrative-card').classList.remove('hidden');

    // Store current event for dismiss
    document.getElementById('narrative-card').dataset.eventKey = event.year + ':' + event.title;
  }

  // ── Layer Toggle Logic ─────────────────────────────────────
  function initLayerToggles() {
    document.querySelectorAll('.layer-toggle input').forEach(function (input) {
      input.addEventListener('change', function () {
        var layerName = input.getAttribute('data-layer');
        var group = input.closest('.layer-group');

        if (input.checked) {
          state.activeLayers.add(layerName);
          group.classList.add('active');
          rebuildLayer(layerName);
          state.layerGroups[layerName].addTo(state.map);
        } else {
          state.activeLayers.delete(layerName);
          group.classList.remove('active');
          state.map.removeLayer(state.layerGroups[layerName]);
        }
      });
    });
  }

  // ── UI Event Handlers ──────────────────────────────────────
  function initUI() {
    // Sidebar toggle (mobile)
    document.getElementById('sidebar-toggle').addEventListener('click', function () {
      document.getElementById('sidebar').classList.toggle('open');
    });

    // Close info panel
    document.getElementById('info-close').addEventListener('click', function () {
      document.getElementById('info-panel').classList.add('hidden');
    });

    // Close narrative
    document.getElementById('narrative-close').addEventListener('click', function () {
      var card = document.getElementById('narrative-card');
      var key = card.dataset.eventKey;
      if (key) state.narrativeDismissed.add(key);
      card.classList.add('hidden');
    });

    // About modal
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

    // Close info panel on map click (if nothing else caught it)
    state.map.on('click', function () {
      document.getElementById('info-panel').classList.add('hidden');
    });

    // Close sidebar on map click (mobile)
    state.map.on('click', function () {
      if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('open');
      }
    });
  }

  // ── Loading Screen ─────────────────────────────────────────
  function showLoading() {
    var overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.id = 'loading';
    overlay.innerHTML = '<div class="loading-spinner"></div><div class="loading-text">Loading map data...</div>';
    document.body.appendChild(overlay);
  }

  function hideLoading() {
    var overlay = document.getElementById('loading');
    if (overlay) {
      overlay.classList.add('fade-out');
      setTimeout(function () { overlay.remove(); }, 600);
    }
  }

  // ── Tooltip CSS injection ──────────────────────────────────
  function injectTooltipStyles() {
    var style = document.createElement('style');
    style.textContent = '' +
      '.dark-tooltip { background: rgba(22,27,34,0.95) !important; color: #e6edf3 !important; ' +
      'border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 6px !important; ' +
      'font-family: Inter, sans-serif !important; font-size: 12px !important; ' +
      'padding: 6px 10px !important; box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important; }' +
      '.dark-tooltip::before { border-top-color: rgba(22,27,34,0.95) !important; }';
    document.head.appendChild(style);
  }

  // ── Boot ───────────────────────────────────────────────────
  async function boot() {
    showLoading();
    injectTooltipStyles();
    initMap();

    await loadAllData();

    initLayerToggles();
    initTimeline();
    initCapitalSelector();
    initPoliticalSelector();
    initUI();

    // Enable redlining by default
    var redliningCheckbox = document.getElementById('layer-redlining');
    redliningCheckbox.checked = true;
    redliningCheckbox.dispatchEvent(new Event('change'));

    // Show initial narrative
    showNarrativeForDecade(state.currentDecade);

    hideLoading();
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
