import {
  useState,
  type FormEvent,
} from "react";

import {
  BrainCircuit,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from "lucide-react";


type LoginPageProps = {
  loading:
    boolean;

  error:
    string | null;

  onLogin:
    (
      email: string,
      password: string
    ) => Promise<void>;
};


export default function LoginPage({
  loading,
  error,
  onLogin,
}: LoginPageProps) {

  const [
    email,
    setEmail,
  ] =
    useState(
      ""
    );


  const [
    password,
    setPassword,
  ] =
    useState(
      ""
    );


  const submit =
    async (
      event:
        FormEvent<HTMLFormElement>
    ) => {

      event
        .preventDefault();

      await onLogin(
        email.trim(),
        password
      );
    };


  return (

    <main className="login-page">

      <section className="login-visual">

        <div className="login-brand">

          <div className="login-brand-icon">

            <BrainCircuit
              size={28}
            />

          </div>


          <div>

            <strong>
              AI Employee
            </strong>

            <span>
              Autonomous Business Development Agent
            </span>

          </div>

        </div>


        <div className="login-hero-copy">

          <div className="login-eyebrow">

            <ShieldCheck
              size={16}
            />

            SECURE AGENT CONTROL PLANE

          </div>


          <h1>
            Human control around
            autonomous execution.
          </h1>


          <p>
            Research, private RAG, lead qualification,
            approval and Gmail actions are now protected
            behind authenticated user access.
          </p>


          <div className="login-security-grid">

            <div>

              <LockKeyhole
                size={19}
              />

              <strong>
                HttpOnly session
              </strong>

              <span>
                Browser JavaScript cannot read the access token.
              </span>

            </div>


            <div>

              <KeyRound
                size={19}
              />

              <strong>
                Role-based access
              </strong>

              <span>
                Admin and operator permissions are enforced by FastAPI.
              </span>

            </div>

          </div>

        </div>

      </section>


      <section className="login-form-side">

        <form
          className="login-card"
          onSubmit={
            submit
          }
        >

          <div className="login-card-heading">

            <span>
              PRIVATE WORKSPACE
            </span>

            <h2>
              Sign in
            </h2>

            <p>
              Use your AI Employee account.
            </p>

          </div>


          <label>

            Email

            <div className="login-input-wrap">

              <Mail
                size={17}
              />

              <input
                type="email"
                autoComplete="username"
                value={
                  email
                }
                onChange={
                  (
                    event
                  ) =>
                    setEmail(
                      event
                        .target
                        .value
                    )
                }
                placeholder="admin@example.com"
                required
              />

            </div>

          </label>


          <label>

            Password

            <div className="login-input-wrap">

              <LockKeyhole
                size={17}
              />

              <input
                type="password"
                autoComplete="current-password"
                value={
                  password
                }
                onChange={
                  (
                    event
                  ) =>
                    setPassword(
                      event
                        .target
                        .value
                    )
                }
                placeholder="Enter password"
                required
              />

            </div>

          </label>


          {
            error
            && (

              <div className="login-error">
                {error}
              </div>
            )
          }


          <button
            className="login-button"
            type="submit"
            disabled={
              loading
            }
          >

            {
              loading
                ? (

                  <LoaderCircle
                    size={18}
                    className="spinning"
                  />

                )
                : (

                  <ShieldCheck
                    size={18}
                  />

                )
            }


            {
              loading
                ? (
                  "Signing in..."
                )
                : (
                  "Sign in securely"
                )
            }

          </button>


          <small className="login-footnote">
            Authentication protects agent execution,
            approval, Gmail, observability and private
            knowledge operations.
          </small>

        </form>

      </section>

    </main>
  );
}

