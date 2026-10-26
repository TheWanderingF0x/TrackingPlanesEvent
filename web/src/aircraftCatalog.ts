/** Auto-generated from config/aircraft_specs.yaml — do not edit by hand. */
/** Run: python scripts/generate_aircraft_catalog.py */

export const AIRCRAFT_NAMES_BY_TYPECODE: Record<string, string> = {
  "A318": "Airbus A318",
  "A319": "Airbus A319-100",
  "A320": "Airbus A320-200",
  "A321": "Airbus A321-200",
  "A20N": "Airbus A320neo",
  "A21N": "Airbus A321neo",
  "A332": "Airbus A330-200",
  "A333": "Airbus A330-300",
  "A339": "Airbus A330-900neo",
  "A343": "Airbus A340-300",
  "A346": "Airbus A340-600",
  "A359": "Airbus A350-900",
  "A35K": "Airbus A350-1000",
  "A388": "Airbus A380-800",
  "AT46": "ATR 42-600",
  "AT75": "ATR 72-500",
  "AT76": "ATR 72-600",
  "B733": "Boeing 737-300",
  "B734": "Boeing 737-400",
  "B737": "Boeing 737-700",
  "B738": "Boeing 737-800",
  "B739": "Boeing 737-900",
  "B38M": "Boeing 737 MAX 8",
  "B39M": "Boeing 737 MAX 9",
  "B744": "Boeing 747-400",
  "B748": "Boeing 747-8",
  "B752": "Boeing 757-200",
  "B763": "Boeing 767-300",
  "B772": "Boeing 777-200",
  "B77L": "Boeing 777-200LR",
  "B77W": "Boeing 777-300ER",
  "B788": "Boeing 787-8",
  "B789": "Boeing 787-9",
  "B78X": "Boeing 787-10",
  "BCS1": "Airbus A220-100",
  "BCS3": "Airbus A220-300",
  "B407": "Bell 407",
  "BE58": "Beechcraft Baron 58",
  "C172": "Cessna 172 Skyhawk",
  "C208": "Cessna 208 Caravan",
  "C525": "Cessna CitationJet",
  "C56X": "Cessna Citation Excel",
  "C650": "Cessna Citation III",
  "CL35": "Bombardier Challenger 350",
  "CL60": "Bombardier Challenger 600",
  "CRJ9": "Bombardier CRJ-900",
  "CRJX": "Bombardier CRJ-1000",
  "DA42": "Diamond DA42 Twin Star",
  "DH8D": "De Havilland Dash 8 Q400",
  "E145": "Embraer ERJ-145",
  "E170": "Embraer E170",
  "E190": "Embraer E190",
  "E195": "Embraer E195",
  "E290": "Embraer E190-E2",
  "E295": "Embraer E195-E2",
  "E300": "Extra EA-300",
  "E35L": "Embraer Legacy 600",
  "E75L": "Embraer E175 (long wing)",
  "E75S": "Embraer E175 (short wing)",
  "EC35": "Airbus Helicopters EC135",
  "EFOX": "Aeropro Eurofox",
  "FA50": "Dassault Falcon 50",
  "FA7X": "Dassault Falcon 7X",
  "GL5T": "Bombardier Global 5000",
  "H25B": "Hawker 800",
  "H900": "Hawker 900XP",
  "PA18": "Piper PA-18 Super Cub",
  "PRM1": "Raytheon Premier 1",
  "SB91": "Saab 91 Safir",
  "SIRA": "Czech Sport Aircraft SportCruiser",
  "ULAC": "Ultralight aircraft"
};

/** Full aircraft name for an ICAO typecode (e.g. B738 → Boeing 737-800). */
export function formatAircraftName(
  typecode?: string | null,
  opts?: { modelName?: string | null; family?: string | null }
): string | null {
  const code = (typecode || "").trim().toUpperCase();
  if (code && code !== "UNKNOWN" && AIRCRAFT_NAMES_BY_TYPECODE[code]) {
    return AIRCRAFT_NAMES_BY_TYPECODE[code];
  }
  const model = (opts?.modelName || "").trim();
  if (model && model.toUpperCase() !== "UNKNOWN") return model;
  const family = (opts?.family || "").trim();
  if (code && code !== "UNKNOWN" && family && family.toUpperCase() !== "UNKNOWN") {
    return `${family} ${code}`;
  }
  if (code && code !== "UNKNOWN") return code;
  if (family && family.toUpperCase() !== "UNKNOWN") return family;
  return null;
}
