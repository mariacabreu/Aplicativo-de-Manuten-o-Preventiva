import React from 'react';
import { TouchableOpacity, Text, ActivityIndicator, StyleSheet, View } from 'react-native';

/**
 * PrimaryButton
 *
 * Botão de ação principal (fundo escuro, texto amarelo), com suporte
 * a estado de carregamento, desabilitado e ícone opcional.
 */
const PrimaryButton = ({ label, onPress, loading = false, disabled = false, style, icon }) => {
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      style={[styles.button, isDisabled && { opacity: 0.6 }, style]}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator size="small" color="#FFCF00" />
      ) : (
        <View style={styles.buttonContent}>
          {icon ? <View style={styles.buttonIcon}>{icon}</View> : null}
          <Text style={styles.buttonText}>{label}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    backgroundColor: '#2E2E2E',
    borderRadius: 15,
    paddingVertical: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonIcon: {
    marginRight: 6,
    flexDirection: 'row',
    alignItems: 'center',
  },
  buttonText: {
    color: '#FFCF00',
    fontSize: 16,
    fontWeight: '700',
  },
});

export default PrimaryButton;