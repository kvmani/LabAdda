import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { Brand } from "../features/home/Brand";
import { BuildFooter } from "../features/shell/BuildFooter";
import { Button } from "../ui";
import "./join.css";

type UnitItem = {
  id: string;
  name: string;
  kind: string;
};

type SubmittedReceipt = {
  id: string;
  fullName: string;
  username: string;
  employeeNo: string;
  unitName: string;
};

export function JoinPage() {
  const [units, setUnits] = useState<UnitItem[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(true);

  // Form fields
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [employeeNo, setEmployeeNo] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [designation, setDesignation] = useState("");
  const [unitSelection, setUnitSelection] = useState("");
  const [customUnitName, setCustomUnitName] = useState("");
  const [interest, setInterest] = useState("");
  const [consented, setConsented] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<SubmittedReceipt | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ units: UnitItem[] }>("/join-requests/units")
      .then((res) => {
        if (!cancelled) {
          setUnits(res.units);
          if (res.units.length > 0 && res.units[0]) {
            setUnitSelection(res.units[0].id);
          } else {
            setUnitSelection("OTHER");
          }
          setLoadingUnits(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUnitSelection("OTHER");
          setLoadingUnits(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const normName = fullName.trim();
    const normUser = username.trim().toLowerCase();
    const normEmp = employeeNo.trim();
    const normEmail = email.trim();
    const normDesig = designation.trim();

    if (!normName) return setError("Please enter your full name.");
    if (!normUser) return setError("Please enter your desired username.");
    if (!/^[a-z0-9][a-z0-9._-]{1,62}$/.test(normUser)) {
      return setError(
        "Username must be 2-63 characters, lowercase letters, numbers, dot, dash, or underscore."
      );
    }
    if (!normEmp) return setError("Please enter your employee / staff identification number.");
    if (!normEmail) return setError("Please enter your official intranet email address.");
    if (!normDesig) return setError("Please state your scientific or technical designation.");

    let finalUnitId: string | null = null;
    let finalCustomUnit: string | null = null;
    let finalDisplayUnitName = "Laboratory Unit";

    if (unitSelection === "OTHER" || units.length === 0) {
      if (!customUnitName.trim()) {
        return setError("Please enter your Division, Section, or Group name.");
      }
      finalCustomUnit = customUnitName.trim();
      finalDisplayUnitName = `${finalCustomUnit} (Proposed new unit)`;
    } else {
      if (!unitSelection) {
        return setError("Please select your research division, section, or group.");
      }
      finalUnitId = unitSelection;
      const found = units.find((u) => u.id === unitSelection);
      if (found) finalDisplayUnitName = found.name;
    }

    if (!consented) {
      return setError(
        "Please confirm the voluntary participation acknowledgment before submitting."
      );
    }

    setBusy(true);
    try {
      const res = await api<{ id: string; status: string; message: string }>("/join-requests", {
        body: {
          full_name: normName,
          username: normUser,
          employee_no: normEmp,
          contact_email: normEmail,
          contact_phone: phone.trim() || null,
          designation: normDesig,
          unit_id: finalUnitId,
          custom_unit_name: finalCustomUnit,
          statement_of_interest: interest.trim() || null,
        },
      });

      setSubmitted({
        id: res.id,
        fullName: normName,
        username: normUser,
        employeeNo: normEmp,
        unitName: finalDisplayUnitName,
      });
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="join-page">
      {/* Header & Brand */}
      <header className="join-page__header">
        <div className="join-page__nav">
          <Brand />
          <Link to="/login" className="join-page__back-link">
            ← Back to Sign in
          </Link>
        </div>
        <div className="join-page__title-group">
          <h1 className="join-page__title">Voluntary Application to Join LabAdda</h1>
          <span className="join-page__badge">Voluntary Participation</span>
        </div>
      </header>

      {/* Friendly Notice Banner */}
      <section className="join-notice" aria-label="Voluntary participation and purpose notice">
        <h2 className="join-notice__title">
          <span aria-hidden="true">🔬</span> About LabAdda & Voluntary Joining
        </h2>
        <p className="join-notice__text">
          LabAdda is an experimental digital collaboration workspace built for our research teams on an
          air-gapped office intranet. Joining this platform is <strong>purely voluntary</strong>. It is
          designed to enhance daily convenience, transparent laboratory communication, and productivity.
        </p>
        <p className="join-notice__text">
          All members are expected to use LabAdda <strong>responsibly</strong>, for the{" "}
          <strong>greater good of collective scientific productivity</strong>, and for{" "}
          <strong>purely professional research purposes</strong>.
        </p>
        <div className="join-notice__callout">
          💡 <em>LabAdda functions as a digital equivalent of our laboratory whiteboards and noticeboards.
          It is not intended for confidential, sensitive, or official secret records.</em>
        </div>
      </section>

      {/* Reference Section: FAQ & Scope */}
      <section className="join-info-grid" aria-label="Reference information and scope">
        {/* FAQ Card */}
        <div className="join-card">
          <h3 className="join-card__title">
            <span aria-hidden="true">❓</span> Frequently Asked Questions
          </h3>
          <div className="join-faq-list">
            <div className="join-faq-item">
              <p className="join-faq-q">Is participation mandatory?</p>
              <p className="join-faq-a">
                No. Participation is 100% voluntary for scientists, technical officers, and research scholars.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">What is LabAdda used for?</p>
              <p className="join-faq-a">
                Noticeboards for unit updates, live whiteboard sessions, experiment task tracking, topic
                chats, and private daily workbench notes.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">How are accounts approved?</p>
              <p className="join-faq-a">
                Laboratory administrators verify your affiliation against staff records and issue a secure,
                one-time activation code to set your password.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">Where is my data stored?</p>
              <p className="join-faq-a">
                Exclusively on our internal laboratory VM on the air-gapped intranet. Zero data ever leaves the
                premises.
              </p>
            </div>
          </div>
        </div>

        {/* Scope & Features Card */}
        <div className="join-card">
          <h3 className="join-card__title">
            <span aria-hidden="true">🚀</span> Key Capabilities & Scope
          </h3>
          <ul className="join-features-list">
            <li className="join-feature-item">
              <span aria-hidden="true">📢</span>
              <span><strong>Noticeboard:</strong> Official lab announcements, pinned notices, and attachments.</span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">🎨</span>
              <span><strong>Live Whiteboard:</strong> Multi-user scientific sketching, equations, and sticky notes.</span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">📋</span>
              <span><strong>Tasks & Checklists:</strong> Research action items, assigned tasks, and deadline reminders.</span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">💬</span>
              <span><strong>Intranet Chat:</strong> Focused, searchable laboratory discussions and project threads.</span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">🔒</span>
              <span><strong>Privacy-First:</strong> Administrators never inspect personal notes or private whiteboard drawings.</span>
            </li>
          </ul>
        </div>
      </section>

      {/* Main Form or Success State */}
      {!submitted ? (
        <form className="join-form" onSubmit={handleSubmit} noValidate>
          <div className="join-form__header">
            <h2 className="join-form__title">Staff Profile Application</h2>
            <p className="join-form__subtitle">
              Please provide your professional laboratory details for administrative verification.
            </p>
          </div>

          {error && (
            <div className="join-form__error" role="alert">
              ⚠️ {error}
            </div>
          )}

          <div className="join-form__grid">
            {/* Full Name */}
            <div className="join-form__field">
              <label htmlFor="full-name" className="join-form__label">
                Full Name <span className="join-form__required">*</span>
              </label>
              <input
                id="full-name"
                type="text"
                className="join-form__input"
                placeholder="e.g. Dr. Sunita Sharma"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
              <p className="join-form__hint">As listed in official laboratory records.</p>
            </div>

            {/* Preferred Username */}
            <div className="join-form__field">
              <label htmlFor="username" className="join-form__label">
                Preferred User ID / Username <span className="join-form__required">*</span>
              </label>
              <input
                id="username"
                type="text"
                className="join-form__input"
                placeholder="e.g. sunita.sharma"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoCapitalize="none"
                autoCorrect="off"
                required
              />
              <p className="join-form__hint">Lowercase alphanumeric, dots, dashes (2-63 chars).</p>
            </div>

            {/* Staff / Employee ID */}
            <div className="join-form__field">
              <label htmlFor="employee-no" className="join-form__label">
                Staff / Employee ID <span className="join-form__required">*</span>
              </label>
              <input
                id="employee-no"
                type="text"
                className="join-form__input"
                placeholder="e.g. EMP-4102"
                value={employeeNo}
                onChange={(e) => setEmployeeNo(e.target.value)}
                required
              />
              <p className="join-form__hint">Used to verify your laboratory affiliation.</p>
            </div>

            {/* Intranet Email */}
            <div className="join-form__field">
              <label htmlFor="email" className="join-form__label">
                Official Intranet Email <span className="join-form__required">*</span>
              </label>
              <input
                id="email"
                type="email"
                className="join-form__input"
                placeholder="e.g. sunita.sharma@nmrl.res.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <p className="join-form__hint">Must belong to our laboratory domain.</p>
            </div>

            {/* Phone / Intercom */}
            <div className="join-form__field">
              <label htmlFor="phone" className="join-form__label">
                Phone / Lab Intercom Extension
              </label>
              <input
                id="phone"
                type="tel"
                className="join-form__input"
                placeholder="e.g. Ext 4412"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <p className="join-form__hint">Optional: for quick laboratory contact.</p>
            </div>

            {/* Designation */}
            <div className="join-form__field">
              <label htmlFor="designation" className="join-form__label">
                Designation / Role <span className="join-form__required">*</span>
              </label>
              <input
                id="designation"
                type="text"
                className="join-form__input"
                placeholder="e.g. Senior Scientist"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                required
              />
              <p className="join-form__hint">Your current scientific or technical designation.</p>
            </div>

            {/* Unit / Division / Group Select */}
            <div className="join-form__field join-form__field--full">
              <label htmlFor="unit-selection" className="join-form__label">
                Home Division, Section, or Group <span className="join-form__required">*</span>
              </label>
              <select
                id="unit-selection"
                className="join-form__select"
                value={unitSelection}
                onChange={(e) => setUnitSelection(e.target.value)}
                disabled={loadingUnits}
                required
              >
                {units.length > 0 && (
                  <>
                    {units.some((u) => u.kind === "org") && (
                      <optgroup label="Divisions & Sections">
                        {units
                          .filter((u) => u.kind === "org")
                          .map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name}
                            </option>
                          ))}
                      </optgroup>
                    )}
                    {units.some((u) => u.kind === "group") && (
                      <optgroup label="Research Groups">
                        {units
                          .filter((u) => u.kind === "group")
                          .map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name}
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </>
                )}
                <option value="OTHER">➕ Other / Not Listed (Enter below)</option>
              </select>
              <p className="join-form__hint">
                Select your unit from the list, or choose "Other / Not Listed" if your unit has not been registered yet.
              </p>
            </div>

            {/* If OTHER or no units in database: show custom unit input */}
            {(unitSelection === "OTHER" || units.length === 0) && (
              <div className="join-form__field join-form__field--full join-form__field--highlight">
                <label htmlFor="custom-unit-name" className="join-form__label">
                  Specify Division / Section / Group Name <span className="join-form__required">*</span>
                </label>
                <input
                  id="custom-unit-name"
                  type="text"
                  className="join-form__input"
                  placeholder="e.g. Surface Engineering Division, or Non-Destructive Testing Section"
                  value={customUnitName}
                  onChange={(e) => setCustomUnitName(e.target.value)}
                  required
                />
                <p className="join-form__hint">
                  Your proposed unit will be verified by the administrator against official records and registered upon account approval.
                </p>
              </div>
            )}

            {/* Statement of Interest */}
            <div className="join-form__field join-form__field--full">
              <label htmlFor="interest" className="join-form__label">
                Research Interest / Intended Use (Optional)
              </label>
              <textarea
                id="interest"
                rows={3}
                className="join-form__textarea"
                placeholder="Briefly mention your research topics or projects you plan to collaborate on..."
                value={interest}
                onChange={(e) => setInterest(e.target.value)}
              />
            </div>
          </div>

          {/* Voluntary Participation Acknowledgment */}
          <div className="join-form__consent">
            <input
              id="consent-check"
              type="checkbox"
              className="join-form__checkbox"
              checked={consented}
              onChange={(e) => setConsented(e.target.checked)}
              required
            />
            <label htmlFor="consent-check" className="join-form__consent-text">
              I understand that joining LabAdda is <strong>purely voluntary</strong>. I agree to use this
              platform responsibly for <strong>professional research collaboration and collective productivity</strong>,
              and understand that it is an air-gapped digital whiteboard not intended for official confidential records.
            </label>
          </div>

          {/* Actions */}
          <div className="join-form__actions">
            <Link to="/login" className="join-page__back-link">
              Cancel
            </Link>
            <Button variant="primary" type="submit" busy={busy} busyLabel="Submitting application…">
              Submit Voluntary Application
            </Button>
          </div>
        </form>
      ) : (
        /* Confirmation State */
        <section className="join-success" aria-label="Application submission confirmation">
          <div className="join-success__icon" aria-hidden="true">
            🎉
          </div>
          <h2 className="join-success__title">Application Submitted Successfully!</h2>
          <p className="join-success__text">
            Thank you, <strong>{submitted.fullName}</strong>. Your voluntary application to join LabAdda
            has been recorded and forwarded to the laboratory administrators for verification.
          </p>

          <div className="join-success__card">
            <div className="join-success__row">
              <span className="join-success__label">Requested User ID:</span>
              <span className="join-success__val">{submitted.username}</span>
            </div>
            <div className="join-success__row">
              <span className="join-success__label">Employee ID:</span>
              <span className="join-success__val">{submitted.employeeNo}</span>
            </div>
            <div className="join-success__row">
              <span className="join-success__label">Selected Unit:</span>
              <span className="join-success__val">{submitted.unitName}</span>
            </div>
          </div>

          <div className="join-success__steps">
            <div className="join-success__step-item">
              <span className="join-success__step-num">1</span>
              <span><strong>Verification:</strong> Administrator verifies your staff affiliation.</span>
            </div>
            <div className="join-success__step-item">
              <span className="join-success__step-num">2</span>
              <span><strong>Activation Code:</strong> You will be issued a one-time activation code.</span>
            </div>
            <div className="join-success__step-item">
              <span className="join-success__step-num">3</span>
              <span><strong>Sign In:</strong> Set your password at <code>/activate</code> and start collaborating!</span>
            </div>
          </div>

          <Link to="/login">
            <Button variant="primary">Return to Sign In</Button>
          </Link>
        </section>
      )}

      <BuildFooter />
    </main>
  );
}
