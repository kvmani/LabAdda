import { Link } from "react-router-dom";
import { Button } from "../../ui";

export type SubmittedReceipt = {
  id: string;
  fullName: string;
  username: string;
  employeeNo: string;
  unitName: string;
};

/** The confirmation after an application is recorded, with what happens next. */
export function JoinSuccess({ submitted }: { submitted: SubmittedReceipt }) {
  return (
    <section className="join-success" aria-label="Application submission confirmation">
      <div className="join-success__icon" aria-hidden="true">
        🎉
      </div>
      <h2 className="join-success__title">Application Submitted Successfully!</h2>
      <p className="join-success__text">
        Thank you, <strong>{submitted.fullName}</strong>. Your voluntary application to join LabAdda has been
        recorded and forwarded to the laboratory administrators for verification.
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
          <span>
            <strong>Verification:</strong> Administrator verifies your staff affiliation.
          </span>
        </div>
        <div className="join-success__step-item">
          <span className="join-success__step-num">2</span>
          <span>
            <strong>Activation Code:</strong> You will be issued a one-time activation code.
          </span>
        </div>
        <div className="join-success__step-item">
          <span className="join-success__step-num">3</span>
          <span>
            <strong>Sign In:</strong> Set your password at <code>/activate</code> and start collaborating!
          </span>
        </div>
      </div>

      <Link to="/login">
        <Button variant="primary">Return to Sign In</Button>
      </Link>
    </section>
  );
}
