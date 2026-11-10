// Raster tiles keep the existing lightweight Leaflet renderer.
// Stadia supports keyless browser development on localhost / 127.0.0.1.
// Configure domain authentication before publishing: https://docs.stadiamaps.com/authentication/
export const BASEMAPS = {
  signal: {
    label: "Signal focus",
    url: "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://stadiamaps.com/attribution/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  streets: {
    label: "Detailed streets",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
};
