import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  icon: ReactNode;
  description: ReactNode;
};

function CrabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width="64" height="64">
      <path d="M8.5 7C5.5 7 3 9.5 3 12.5C3 15.5 5.5 18 8.5 18H15.5C18.5 18 21 15.5 21 12.5C21 9.5 18.5 7 15.5 7H8.5ZM8.5 9C6 9 4 11 4 13.5C4 16 6 17.5 8.5 17.5C11 17.5 13 16 13 13.5C13 11 11 9 8.5 9ZM15.5 9C13 9 11 11 11 13.5C11 16 13 17.5 15.5 17.5C18 17.5 20 16 20 13.5C20 11 18 9 15.5 9Z"/>
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width="64" height="64">
      <path d="M12 15.5A3.5 3.5 0 0 1 8.5 12A3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5a3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97c0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1c0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66Z"/>
    </svg>
  );
}

function UnlockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width="64" height="64">
      <path d="M10 13a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-2m6-2V8a4 4 0 0 0-4-4 4 4 0 0 0-4 4h2a2 2 0 0 1 2-2 2 2 0 0 1 2 2v3H8a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2h-2Z"/>
    </svg>
  );
}

const FeatureList: FeatureItem[] = [
  {
    title: 'Universal Claw Support',
    icon: <CrabIcon />,
    description: (
      <>
        Manage any claw from a single command center: OpenClaw, ZeroClaw,
        NemoClaw, NanoClaw, IronClaw, and more.
      </>
    ),
  },
  {
    title: 'Normalized Configuration',
    icon: <GearIcon />,
    description: (
      <>
        One config format for every claw. Define your preferences once and
        Clawrium translates them for each claw&apos;s native format.
      </>
    ),
  },
  {
    title: 'Multi-Model Freedom',
    icon: <UnlockIcon />,
    description: (
      <>
        Run any model across your fleet: open models like Nemotron,
        providers like OpenAI and Anthropic, or local with Ollama.
      </>
    ),
  },
];

function Feature({title, icon, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <div className={styles.featureIcon}>{icon}</div>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
