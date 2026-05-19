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
        }}
      >
        See you tomorrow morning.
      </p>
    </div>
  );
}
