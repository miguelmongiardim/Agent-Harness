# Research Foundations

This document records public, self-contained references that inform Agent
Harness V0. Private or local planning notes may influence implementation
decisions, but they are not required sources for understanding the public
project.

## Agent And Retrieval Patterns

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)
- [SWE-bench](https://www.swebench.com/)

## Security And Risk Management

- [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [OWASP Agentic Security Initiative](https://genai.owasp.org/initiatives/agentic-security-initiative/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/projects/ssdf)

## Ecosystem References

- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain human-in-the-loop documentation](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Model Context Protocol documentation](https://modelcontextprotocol.io/docs)

## V0 Interpretation

Agent Harness V0 applies these references conservatively:

- RAG informs context manifest provenance and retrieval boundaries, but V0
  keeps retrieval local and deterministic by default.
- ReAct informs the plan-act-observe loop, but V0 uses a deterministic mock
  model rather than a network model provider.
- Lost in the Middle motivates small, explicit context packs rather than
  indiscriminate long-context stuffing.
- SWE-bench motivates software-engineering eval scenarios, but V0 ships small
  bundled fixtures rather than claiming benchmark comparability.
- OWASP and NIST references motivate policy ceilings, least privilege,
  untrusted evidence handling, approval gates, auditability, and report-only
  scanner posture for non-critical findings.
