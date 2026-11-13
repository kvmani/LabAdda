import { BASE } from "../../config";

/** Locally bundled approved LabAdda identity. */
export function Brand() {
  return (
    <span className="brand">
      <img src={`${BASE}/logo.png`} alt="" />
      <span>LabAdda</span>
    </span>
  );
}
