import * as readline from "readline";
import { emailAgent } from "./agent.js";

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

async function main() {
  console.log("AgentMail Mastra Agent");
  console.log("======================");
  console.log("Try: 'Create an inbox for sales outreach'");
  console.log("     'Send an email to test@example.com about the meeting'");
  console.log("     'Check my inbox for new messages'");
  console.log("Type 'exit' to quit.\n");

  const prompt = () => {
    rl.question("You: ", async (input) => {
      const trimmed = input.trim();
      if (trimmed.toLowerCase() === "exit") {
        rl.close();
        return;
      }
      if (!trimmed) {
        prompt();
        return;
      }

      try {
        const response = await emailAgent.generate(trimmed);
        console.log(`\nAgent: ${response.text}\n`);
      } catch (error: any) {
        console.error(`Error: ${error.message}\n`);
      }

      prompt();
    });
  };

  prompt();
}

main();
