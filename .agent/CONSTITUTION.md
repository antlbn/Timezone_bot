# Project Constitution: The Algorithm

This document defines the core philosophy and development methodology for the Timezone Bot project.

## 1. The Algorithm (Musk's 5 Steps)

All development and optimization efforts must follow these steps in order:

1.  **Make Requirements Less Dumb**: Question every requirement. Each must have a specific owner and a clear "why". Requirements from smart people are often the most dangerous because they are less likely to be questioned.
2.  **Delete the Part or Process**: Try as hard as you can to delete the part or process. If you are not adding back at least 10% of what you deleted, you are not deleting enough.
3.  **Simplify or Optimize**: Only after steps 1 and 2 are complete should you try to simplify or optimize. A common mistake is optimizing something that shouldn't exist.
4.  **Accelerate Cycle Time**: Once the process is lean and optimized, increase the speed. If you didn't do steps 1-3 first, you are just digging your grave faster.
5.  **Automate**: The final step is automation. Never automate a process that hasn't been through the first 4 steps.

## 2. Core Principles

-   **Occam's Razor for Code**: Do not multiply entities beyond necessity. If a problem can be solved with fewer objects, services, or layers, do it.
-   **Look Back and Purge**: Periodically review existing code and architectures. Ask: "If I were starting from scratch, would I build this? Does it still serve a purpose?" If the answer is no, delete it.
-   **Robustness via Simplicity**: Complexity is a failure of design. True robustness comes from having fewer moving parts that can break.
-   **Zero Friction**: Focus on the end-user (and developer) experience. Any step that can be removed to make the system more intuitive should be removed.
