import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  LoaderCircle,
  LogOut,
  ShieldCheck,
} from "lucide-react";

import App from "../App";

import {
  api,
} from "../api";

import LoginPage from "./LoginPage";

import "./auth.css";


type AuthUser = {
  id:
    number;

  email:
    string;

  role:
    "admin"
    |
    "operator";

  is_active:
    boolean;

  created_at?:
    string;

  last_login_at?:
    string;
};


export default function AuthRoot() {

  const [
    user,
    setUser,
  ] =
    useState<
      AuthUser
      |
      null
    >(
      null
    );


  const [
    checking,
    setChecking,
  ] =
    useState(
      true
    );


  const [
    loginLoading,
    setLoginLoading,
  ] =
    useState(
      false
    );


  const [
    loginError,
    setLoginError,
  ] =
    useState<
      string
      |
      null
    >(
      null
    );


  const checkSession =
    useCallback(
      async () => {

        try {

          const response =
            await api.get(
              "/auth/me"
            );


          setUser(
            response
              .data
              ?.user
            ??
            null
          );

        } catch {

          setUser(
            null
          );

        } finally {

          setChecking(
            false
          );
        }
      },

      []
    );


  useEffect(
    () => {

      void checkSession();

    },
    [
      checkSession
    ]
  );


  useEffect(
    () => {

      const expired =
        () => {

          setUser(
            null
          );

          setLoginError(
            "Your session expired. Please sign in again."
          );
        };


      window.addEventListener(
        "auth:expired",
        expired
      );


      return () => {

        window.removeEventListener(
          "auth:expired",
          expired
        );
      };

    },
    []
  );


  const login =
    async (
      email:
        string,

      password:
        string
    ) => {

      setLoginLoading(
        true
      );

      setLoginError(
        null
      );


      try {

        const response =
          await api.post(
            "/auth/login",
            {
              email,
              password,
            }
          );


        setUser(
          response
            .data
            ?.user
          ??
          null
        );

      } catch (
        error: any
      ) {

        setUser(
          null
        );

        setLoginError(
          error
            ?.response
            ?.data
            ?.detail
          ??
          error
            ?.message
          ??
          "Sign in failed."
        );

      } finally {

        setLoginLoading(
          false
        );
      }
    };


  const logout =
    async () => {

      try {

        await api.post(
          "/auth/logout"
        );

      } catch {

        // Even if the backend is unavailable,
        // remove the authenticated UI locally.
      }


      setUser(
        null
      );

      setLoginError(
        null
      );
    };


  if (
    checking
  ) {

    return (

      <div className="auth-loading-screen">

        <LoaderCircle
          size={30}
          className="spinning"
        />

        <strong>
          Checking secure session...
        </strong>

      </div>
    );
  }


  if (
    !user
  ) {

    return (

      <LoginPage
        loading={
          loginLoading
        }
        error={
          loginError
        }
        onLogin={
          login
        }
      />
    );
  }


  return (

    <div className="authenticated-app">

      <App />


      <div className="session-chip">

        <div className="session-shield">

          <ShieldCheck
            size={17}
          />

        </div>


        <div className="session-copy">

          <strong>
            {
              user.email
            }
          </strong>

          <span>

            {
              user.role
                .toUpperCase()
            }

            {" · Authenticated"}

          </span>

        </div>


        <button
          type="button"
          className="session-logout"
          onClick={
            logout
          }
          title="Sign out"
        >

          <LogOut
            size={16}
          />

        </button>

      </div>

    </div>
  );
}

