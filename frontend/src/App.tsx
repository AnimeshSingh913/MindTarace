import { Analyzer } from "@/components/Analyzer";
import { Hero } from "@/components/Hero";
import { Logo } from "@/components/Logo";
import { Modes } from "@/components/Modes";
import { Nav } from "@/components/Nav";
import { Safety } from "@/components/Safety";

const App = () => (
  <div className="min-h-screen">
    <Nav />
    <main>
      <Hero />
      <Analyzer />
      <Modes />
      <Safety />
    </main>
    <footer className="container-page flex flex-col items-center justify-between gap-3 py-10 text-sm text-subtle sm:flex-row">
      <span className="flex items-center gap-2 font-semibold text-fg">
        <Logo className="h-5 w-5" /> MindTrace
      </span>
      <span>Explains mistakes. Never gives answers. Runs locally with Ollama.</span>
    </footer>
  </div>
);

export default App;
