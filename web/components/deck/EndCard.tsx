export default function EndCard() {
  return (
    <div
      style={{
        position: 'relative',
        height: '100dvh',
        width: '100%',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 32px',
        textAlign: 'center',
      }}
    >
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '28px',
          fontWeight: 500,
          lineHeight: 1.2,
          marginBottom: '16px',
        }}
      >
        That&apos;s the signal for today.
      </p>
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '17px',
          color: 'var(--muted)',
          marginBottom: '28px',
        }}
      >
        See you tomorrow morning.
      </p>

      {/* Beta feedback */}
      <a
        href="mailto:sanchitpurdue@gmail.com?subject=DING%20beta%20feedback"
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--muted)',
          textDecoration: 'none',
          borderBottom: '1px solid var(--divider)',
          paddingBottom: '2px',
          marginBottom: '56px',
        }}
      >
        Send feedback
      </a>

      {/* Branding */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        {/* Wordmark */}
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '22px',
            fontWeight: 700,
            letterSpacing: '0.18em',
            color: 'var(--accent)',
          }}
        >
          DING
        </p>
        {/* Divider */}
        <div style={{ width: '24px', height: '1px', background: 'var(--divider)' }} />
        {/* Tagline */}
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--subtle)',
          }}
        >
          Morning Signal · AI-curated
        </p>
      </div>
    </div>
  );
}
