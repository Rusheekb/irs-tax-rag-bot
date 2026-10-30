"""Chat page for the IRS tax bot. Run with: streamlit run app.py"""
import re

import streamlit as st

from bot import ask

st.set_page_config(page_title="IRS Tax Guide Bot")
st.title("IRS Tax Guide Bot")
st.caption(
    "Explains U.S. federal tax rules for tax year 2025 from four IRS publications. "
    "This is a study aid, not tax advice. Check every answer against its source."
)

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_sources(sources):
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for source in sources:
                st.markdown(f"**{source['file']}**")
                # Parsed passages contain Markdown headings that would render huge here.
                st.caption(re.sub(r"#+\s*", "", source["text"])[:600] + "...")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        show_sources(message.get("sources"))

if question := st.chat_input("Ask about the 2025 federal tax rules"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the IRS documents..."):
                result = ask(question)
        except Exception as error:
            st.error(f"Couldn't reach AWS. Try running `aws login`. Details: {error}")
            st.stop()
        st.markdown(result["answer"])
        if result["blocked"]:
            st.info("The guardrail blocked an answer the documents didn't support.")
        show_sources(result["sources"])

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
