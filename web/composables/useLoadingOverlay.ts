export default function useLoadingOverlay() {
  const isLoading = useState('isLoading', () => false);
  const message = useState('message', () => '');

  function show(messageText: string) {
    isLoading.value = true;
    message.value = messageText;
  }
  function hide() {
    isLoading.value = false;
    message.value = '';
  }

  return {
    isLoading,
    message,
    show,
    hide,
    async transaction(callback: () => void, messageText: string) {
      show(messageText);
      try {
        await callback();
      } finally {
        hide();
      }
    }
  };
}