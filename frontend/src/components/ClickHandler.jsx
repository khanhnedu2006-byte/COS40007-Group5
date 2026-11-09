import { useMapEvents } from "react-leaflet";

export default function ClickHandler({ onMapClick, disabled }) {
  useMapEvents({
    click: ({ latlng }) => { if (!disabled) onMapClick(latlng.lat, latlng.lng); },
  });
  return null;
}
