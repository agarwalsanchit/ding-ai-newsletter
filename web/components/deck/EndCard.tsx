import Card from './Card';

export default function EndCard() {
  return (
    <Card>
      <div style={{ textAlign: 'center' }}>
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
    </Card>
  );
}
